import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ReactFlow, Background, BackgroundVariant, ConnectionMode,
  useNodesState, useEdgesState, addEdge, useReactFlow, ReactFlowProvider, MarkerType, useStore,
  type Node, type Edge, type Connection, type NodeChange, type EdgeChange,
} from '@xyflow/react'

import { py, cho_cau_noi } from './api'
import type { Bootstrap, Card, ProcEdge, Problem, ProcessDoc, Step, StepKind } from './types'
import Ribbon from './components/Ribbon'
import StepNode from './components/StepNode'
import StepDialog from './components/StepDialog'
import ActionDialog from './components/ActionDialog'
import SettingsDialog from './components/SettingsDialog'
import TemplatePicker from './components/TemplatePicker'
import type { MucMenu } from './components/Ribbon'

const nodeTypes = { buoc: StepNode }

/** Mũi tên chỉ cần đủ để biết dây chạy về hướng nào. To quá thì nó nặng hơn cả cái
 *  cổng nó cắm vào (cổng 9px, mũi tên cũ 16px) và hút mắt khỏi nội dung khối. */
const MUI_TEN = { type: MarkerType.ArrowClosed, width: 10, height: 10, color: '#6a6a6a' }

/** 'default' = đường bezier. Cố ý KHÔNG dùng 'smoothstep': hộp cao thấp khác nhau nên
 *  hai đầu nối hiếm khi cùng độ cao, đường bậc thang gãy khúc trông như lỗi vẽ. */
const KIEU_DUONG_NOI = { type: 'default', animated: false, markerEnd: MUI_TEN }

/** Giữ Ctrl HOẶC Shift rồi bấm để chọn thêm khối. Shift cũng là phím quét-khung
 *  mặc định của React Flow, nên Shift+kéo trên nền vẫn quét chọn nhiều khối. */
const PHIM_CHON_NHIEU = ['Control', 'Meta', 'Shift']

/* ---------- đổi qua lại giữa tài liệu của Python và node/edge của React Flow ---------- */

function doc_sang_rf(doc: ProcessDoc): { nodes: Node[]; edges: Edge[] } {
  const theo_id = new Map(doc.cards.map(c => [c.id, c]))
  const nodes: Node[] = doc.steps.map((s, i) => ({
    id: s.id,
    type: 'buoc',
    position: { x: s.pos?.[0] ?? 80 + i * 330, y: s.pos?.[1] ?? 120 },
    data: { step: s, card: theo_id.get(s.id) as Card },
  }))
  const edges: Edge[] = doc.edges.map(e => ({
    id: `${e.from}->${e.to}:${e.port}`,
    source: e.from,
    target: e.to,
    // Mặc định phải→trái: luồng chạy trái sang phải, nên đường nối đi ra cạnh phải
    // của hộp trước và vào cạnh trái của hộp sau.
    sourceHandle: (e as { from_side?: string }).from_side ?? 'right',
    targetHandle: (e as { to_side?: string }).to_side ?? 'left',
    markerEnd: MUI_TEN,
  }))
  return { nodes, edges }
}

function rf_sang_steps(nodes: Node[]): Step[] {
  return nodes.map(n => ({
    ...(n.data as { step: Step }).step,
    pos: [Math.round(n.position.x), Math.round(n.position.y)] as [number, number],
  }))
}

function rf_sang_edges(edges: Edge[]): ProcEdge[] {
  return edges.map(e => ({
    from: e.source,
    to: e.target,
    port: 'out',
    from_side: e.sourceHandle ?? 'right',
    to_side: e.targetHandle ?? 'left',
  })) as ProcEdge[]
}

/* ---------------------------------- Undo ---------------------------------- */

interface Anh { nodes: Node[]; edges: Edge[]; ten: string }

const TOI_DA_UNDO = 60

/** Bảng dưới: cao tối thiểu khi kéo, và cao khi đã gập (vừa đủ hàng tab). */
const CAO_TOI_THIEU = 90
const CAO_GAP = 33

/** Bộ nhớ tạm Ctrl+C/Ctrl+V cho KHỐI trên canvas. Giữ cả đường nối GIỮA các khối
 *  được chép — chép 3 khối đang nối nhau mà mất dây thì coi như chép hụt.
 *  Dùng bộ nhớ trong app, không dùng clipboard hệ điều hành: clipboard thật đang
 *  phục vụ luồng đọc chữ item trong game. */
let boNhoKhoi: { steps: Step[]; edges: ProcEdge[] } = { steps: [], edges: [] }

/* --------------------------------- App ----------------------------------- */

function Ung() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [ten, setTen] = useState('Process 1')
  const [startDelay, setStartDelay] = useState(3)
  const [vanDe, setVanDe] = useState<Problem[]>([])
  const [tab, setTab] = useState<'van-de' | 'nhat-ky'>('van-de')
  const [nhatKy, setNhatKy] = useState<{ gio: string; msg: string; tag?: string | null }[]>([])
  const [dangChay, setDangChay] = useState(false)
  const [phimDung, setPhimDung] = useState('F6')
  const [sanSang, setSanSang] = useState(false)
  const [trangThai, setTrangThai] = useState('đang khởi động…')
  const [boot, setBoot] = useState<Bootstrap | null>(null)
  const [mods, setMods] = useState<string[]>([])
  /** Bước đang mở hộp thoại. Loop/Nhóm mở StepDialog, HĐ lẻ mở thẳng ActionDialog. */
  const [dangSua, setDangSua] = useState<string | null>(null)
  /** {id khối -> số thứ tự chạy}. Do Python tính, không phải JS đếm. */
  /* Nhãn bước: CHUỖI chứ không phải số — có rẽ nhánh rồi thì "4A.2B" mới nói đủ. */
  const [thuTu, setThuTu] = useState<Record<string, string>>({})
  const [coVong, setCoVong] = useState(false)
  /** Bảng dưới: chiều cao kéo được, và gập lại còn mỗi hàng tab. */
  const [panelCao, setPanelCao] = useState(176)
  const [panelGap, setPanelGap] = useState(false)
  /** Đang kéo một đường nối. Bật lên thì MỌI cổng của MỌI khối hiện rõ — không thì
      phải đoán xem thả vào đâu được. */
  const [dangNoi, setDangNoi] = useState(false)
  const [moCaiDat, setMoCaiDat] = useState(false)
  /** Hộp chọn template đang mở: kind + việc sẽ làm với cái được chọn. */
  const [moPicker, setMoPicker] = useState<
    { kind: 'process' | 'loop' | 'group'; tieuDe: string; xong: (t: string) => void } | null>(null)
  const { fitView, zoomIn, zoomOut, setCenter, screenToFlowPosition } = useReactFlow()
  /* Mức thu phóng phải ĐĂNG KÝ THEO DÕI, không gọi getZoom() lúc render: React Flow
     đổi viewport không làm component này vẽ lại, nên con số đứng im mãi ở giá trị
     lúc render lần cuối (lỗi có sẵn — bấm zoom mà số không nhúc nhích). */
  const mucZoom = useStore(st => st.transform[2])

  const lui = useRef<Anh[]>([])
  const toi = useRef<Anh[]>([])
  const cuoiLog = useRef<HTMLDivElement>(null)
  const [coLui, setCoLui] = useState(false)
  const [coToi, setCoToi] = useState(false)

  /** Đổi màu nhấn tức thì. Chỉ cần ghi đè một biến CSS — đây chính là lý do
   *  theme dùng biến chứ không viết cứng màu ở từng chỗ. */
  const doiMauNgay = useCallback((mau: string) => {
    document.documentElement.style.setProperty('--accent', mau)
    document.documentElement.style.setProperty('--accent-soft', mau + '2b')
  }, [])

  const ghi = useCallback((m: string, tag?: string | null) => {
    const gio = new Date().toLocaleTimeString('vi-VN', { hour12: false })
    setNhatKy(x => [...x.slice(-600), { gio, msg: m, tag }])
  }, [])

  /** Chụp trạng thái TRƯỚC khi thay đổi. Ảnh chụp nguyên khối thay vì tính diff:
   *  tài liệu chỉ vài chục KB, mà diff sai thì undo hỏng theo kiểu rất khó tìm. */
  const chup = useCallback(() => {
    lui.current.push({ nodes, edges, ten })
    if (lui.current.length > TOI_DA_UNDO) lui.current.shift()
    toi.current = []
    setCoLui(true); setCoToi(false)
  }, [nodes, edges, ten])

  const apDung = useCallback((a: Anh) => {
    setNodes(a.nodes); setEdges(a.edges); setTen(a.ten)
  }, [setNodes, setEdges])

  const hoanTac = useCallback(() => {
    const a = lui.current.pop()
    if (!a) return
    toi.current.push({ nodes, edges, ten })
    apDung(a)
    setCoLui(lui.current.length > 0); setCoToi(true)
    setTrangThai('đã hoàn tác')
  }, [nodes, edges, ten, apDung])

  const lamLai = useCallback(() => {
    const a = toi.current.pop()
    if (!a) return
    lui.current.push({ nodes, edges, ten })
    apDung(a)
    setCoToi(toi.current.length > 0); setCoLui(true)
    setTrangThai('đã làm lại')
  }, [nodes, edges, ten, apDung])

  /* ------------------------------ khởi động ------------------------------ */
  useEffect(() => {
    (async () => {
      try {
        await cho_cau_noi()
        const b = await py.bootstrap()
        if (!b.ok) { setTrangThai('lỗi bootstrap: ' + b.error); return }
        setBoot(b.value!)
        const mau = (b.value!.settings as any)?.accent
        if (mau) doiMauNgay(String(mau))
        const ui = (b.value!.settings as any)?.ui || {}
        if (ui.panel_cao) setPanelCao(Math.max(CAO_TOI_THIEU, Math.min(600, Number(ui.panel_cao))))
        if (ui.panel_gap) setPanelGap(true)
        // Nạp cả 3223 mod MỘT lần rồi lọc trong JS. Lọc ở Python theo từng phím gõ
        // thì mỗi ký tự là một vòng promise; đo được cả danh sách chỉ mất 7ms.
        py.get_mods().then(r => r.ok && setMods(r.value ?? []))
        const ds = await py.list_templates('process')
        const co = (ds.ok && (ds.value?.length ?? 0) > 0)
        const r = co ? await py.load_process(ds.value![0]) : await py.demo_process()
        if (r.ok && r.value) {
          const { nodes: n, edges: e } = doc_sang_rf(r.value)
          setNodes(n); setEdges(e); setTen(r.value.name); setStartDelay(r.value.start_delay)
          ghi(co ? `mở template "${ds.value![0]}"` : 'chưa có template — đang xem Process mẫu')
        }
        setSanSang(true)
        setTrangThai('sẵn sàng')
        setTimeout(() => fitView({ padding: 0.2, duration: 300 }), 60)
      } catch (e) {
        setTrangThai('không kết nối được Python: ' + String(e))
      }
    })()
    // chỉ chạy 1 lần lúc mở app
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /* --------------------------- kiểm tra liên tục -------------------------- */
  useEffect(() => {
    if (!sanSang) return
    const h = setTimeout(async () => {
      const r = await py.validate(rf_sang_steps(nodes), rf_sang_edges(edges))
      if (!r.ok) return
      setVanDe(r.value ?? [])
      // Số thứ tự do PYTHON tính, bằng chính phép duyệt mà bộ máy chạy dùng —
      // JS không tự đếm, nếu không con số lại nói khác thực tế.
      const o = (r as any).order as Record<string, string>
      setThuTu(o ?? {})
      setCoVong(!!(r as any).loop)
    }, 250)   // gộp lại: kéo hộp bắn ra hàng chục thay đổi mỗi giây
    return () => clearTimeout(h)
  }, [nodes, edges, sanSang])

  /* Tên Process nằm ở THANH TIÊU ĐỀ cửa sổ, không phải một ô nhập chiếm 263px.
     Hoãn 400ms vì gõ từng chữ mà gọi sang Python mỗi phím thì phí cầu nối. */
  useEffect(() => {
    if (!sanSang) return
    const h = setTimeout(() => { py.set_title(ten) }, 400)
    return () => clearTimeout(h)
  }, [ten, sanSang])

  /** Đổi tên Process — double-click nền canvas, hoặc menu Template. */
  const doiTenProcess = useCallback(() => {
    const moi = window.prompt('Tên Process:', ten)
    if (moi == null) return
    const t = moi.trim()
    if (t && t !== ten) { chup(); setTen(t); ghi(`đổi tên Process thành "${t}"`) }
  }, [ten, chup, ghi])

  /* Ghi nhớ bố cục bảng dưới. Hoãn 500ms: kéo chuột bắn ra hàng chục thay đổi,
     ghi file mỗi lần thì phí. */
  useEffect(() => {
    if (!sanSang) return
    const h = setTimeout(() => { py.save_ui({ panel_cao: panelCao, panel_gap: panelGap }) }, 500)
    return () => clearTimeout(h)
  }, [panelCao, panelGap, sanSang])

  /** Kéo mép trên bảng dưới để chỉnh chiều cao. Bám theo con trỏ cho tới khi thả,
   *  kể cả khi chuột đi ra ngoài cửa sổ — nếu chỉ nghe trên chính thanh kéo thì
   *  kéo nhanh một cái là mất dấu. */
  const batDauKeoPanel = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    if (panelGap) setPanelGap(false)
    const y0 = e.clientY
    const cao0 = panelGap ? CAO_GAP : panelCao
    const di = (ev: MouseEvent) =>
      setPanelCao(Math.max(CAO_TOI_THIEU, Math.min(600, cao0 + (y0 - ev.clientY))))
    const thoi = () => {
      window.removeEventListener('mousemove', di)
      window.removeEventListener('mouseup', thoi)
      document.body.style.cursor = ''
    }
    document.body.style.cursor = 'ns-resize'
    window.addEventListener('mousemove', di)
    window.addEventListener('mouseup', thoi)
  }, [panelCao, panelGap])

  /* Nhật ký tự cuộn xuống đáy — đang chạy mà phải cuộn tay thì không theo dõi nổi. */
  useEffect(() => {
    if (tab === 'nhat-ky') cuoiLog.current?.scrollIntoView({ block: 'end' })
  }, [nhatKy, tab])

  /* ------------------------------ thao tác ------------------------------- */
  const dangChon = useMemo(() => nodes.filter(n => n.selected), [nodes])

  /** Vị trí con trỏ mới nhất, toạ độ màn hình.
   *
   *  Cố ý dùng `useRef` chứ không phải `useState`: chuột bắn ra hàng trăm sự kiện mỗi
   *  giây, để vào state là vẽ lại toàn bộ canvas theo từng cái nhích chuột. Ref ghi
   *  thẳng, không kích hoạt render nào. */
  const viTriChuot = useRef<{ x: number; y: number } | null>(null)
  useEffect(() => {
    const f = (e: MouseEvent) => { viTriChuot.current = { x: e.clientX, y: e.clientY } }
    window.addEventListener('mousemove', f)
    return () => window.removeEventListener('mousemove', f)
  }, [])

  /** Điểm dán, theo toạ độ CANVAS (đã tính cả thu phóng và cuộn).
   *
   *  Con trỏ không nằm trên canvas — đang ở ribbon, ở bảng dưới, hoặc chưa rê lần nào
   *  — thì lấy GIỮA khung nhìn. Điều thật sự cần bảo đảm là khối dán ra phải NHÌN THẤY
   *  ĐƯỢC; giữa khung nhìn luôn thoả điều đó, còn "lệch 40px từ bản gốc" thì không. */
  const diemDan = useCallback(() => {
    const khung = document.querySelector('.vung-canvas')?.getBoundingClientRect()
    if (!khung) return null
    const c = viTriChuot.current
    const trong = !!c && c.x >= khung.left && c.x <= khung.right
                       && c.y >= khung.top && c.y <= khung.bottom
    return screenToFlowPosition(trong ? c! : {
      x: khung.left + khung.width / 2, y: khung.top + khung.height / 2,
    })
  }, [screenToFlowPosition])

  const themKhoi = useCallback(async (kind: StepKind, loaiHD?: string) => {
    const r = await py.new_step(kind, loaiHD)
    if (!r.ok || !r.value) { ghi('không tạo được khối: ' + r.error); return }
    chup()
    const { step, card } = r.value
    const x = nodes.length ? Math.max(...nodes.map(n => n.position.x)) + 420 : 80
    const y = nodes.length ? nodes[nodes.length - 1].position.y : 120
    const moi: Node = { id: step.id, type: 'buoc', position: { x, y }, data: { step, card } }
    setNodes(n => [...n.map(k => ({ ...k, selected: false })), { ...moi, selected: true }])
    ghi(`thêm khối ${card.title}`)
    // Mở luôn hộp thoại của khối vừa thêm. Loop/Nhóm mới là RỖNG, còn HĐ lẻ thì mặc
    // định là một Trái-click giữa màn hình — cả ba đều vô nghĩa cho tới khi cấu hình.
    // Bắt người dùng đi tìm rồi double-click là một bước thừa không đổi lại được gì.
    // Chỉ muốn cái khối thôi thì Esc là xong.
    setDangSua(step.id)
  }, [nodes, chup, setNodes, ghi])

  const xoa = useCallback(() => {
    if (!dangChon.length) return
    chup()
    const bo = new Set(dangChon.map(n => n.id))
    setNodes(n => n.filter(k => !bo.has(k.id)))
    setEdges(e => e.filter(k => !bo.has(k.source) && !bo.has(k.target)))
    ghi(`xoá ${bo.size} khối`)
  }, [dangChon, chup, setNodes, setEdges, ghi])

  const doiTen = useCallback(() => {
    const n = dangChon[0]
    if (!n) return
    const cu = (n.data as { card: Card }).card.title
    const moi = window.prompt('Tên khối:', cu)
    if (moi == null) return
    chup()
    setNodes(ds => ds.map(k => {
      if (k.id !== n.id) return k
      const d = k.data as { step: Step; card: Card }
      const ten_moi = moi.trim() || cu
      return { ...k, data: { step: { ...d.step, name: ten_moi }, card: { ...d.card, title: ten_moi } } }
    }))
  }, [dangChon, chup, setNodes])

  const nhanBan = useCallback(async () => {
    const n = dangChon[0]
    if (!n) return
    const d = n.data as { step: Step; card: Card }
    // Id do core cấp — JS không tự nặn định dạng id.
    const r = await py.clone_steps([d.step])
    if (!r.ok || !r.value) { ghi('không nhân bản được: ' + r.error, 'err'); return }
    chup()
    const step = r.value.steps[0]
    const card = { ...r.value.cards[0], title: r.value.cards[0].title + ' (bản sao)' }
    step.name = card.title
    setNodes(ds => [...ds.map(k => ({ ...k, selected: false })), {
      id: step.id, type: 'buoc', position: { x: n.position.x + 40, y: n.position.y + 60 },
      data: { step, card }, selected: true,
    }])
    ghi('nhân bản khối')
  }, [dangChon, chup, setNodes, ghi])

  /** Ghi bước đã sửa trở lại node, và LẤY LẠI nội dung hộp từ Python — không tự dựng
   *  lại thẻ ở JS, nếu không hộp sẽ mô tả khác với những gì core thực sự hiểu. */
  const ghiBuoc = useCallback(async (s: Step) => {
    const r = await py.describe([s])
    const card = r.ok ? r.value![0] : null
    chup()
    setNodes(ds => ds.map(k => (k.id === s.id
      ? { ...k, data: { step: s, card: card ?? (k.data as { card: Card }).card } }
      : k)))
    setDangSua(null)
    ghi(`sửa "${card?.title ?? s.name ?? s.id}"`)
  }, [chup, setNodes, ghi])

  /* ------------------------------ chạy / dừng ----------------------------- */
  /* Python ĐẨY diễn biến sang đây (đã gom lô 150ms một lần ở phía Python — mỗi lần
     qua cầu nối là một vòng IPC, đẩy từng dòng sẽ ngốn hết luồng giao diện). */
  useEffect(() => {
    ;(window as any).__su_kien = (ten: string, d: any) => {
      if (ten !== 'run') return
      if (d.status) setTrangThai(d.status)
      if (d.log?.length) {
        const gio = new Date().toLocaleTimeString('vi-VN', { hour12: false })
        setNhatKy(x => [...x, ...d.log.map((l: any) => ({ gio, msg: l.msg, tag: l.tag }))].slice(-600))
        const cuoi = d.log[d.log.length - 1]
        if (cuoi?.het) {
          setDangChay(false)
          setTrangThai(cuoi.msg)
        }
      }
    }
    return () => { delete (window as any).__su_kien }
  }, [])

  const chay = useCallback(async (boQua = false) => {
    const steps = rf_sang_steps(nodes)
    const r = await py.run(ten, steps, startDelay, boQua)
    if (!r.ok) {
      if ((r as any).can_hoi) {
        const ds = ((r as any).canh_bao as Problem[]).map(p => '⚠ ' + p.message).join('\n\n')
        if (window.confirm(ds + '\n\nVẫn chạy?')) chay(true)
        return
      }
      const ds = ((r as any).loi as Problem[] | undefined)?.map(p => '✖ ' + p.message).join('\n\n')
      window.alert((r.error ?? 'không chạy được') + (ds ? '\n\n' + ds : ''))
      return
    }
    setPhimDung(r.value?.hotkey ?? 'F6')
    setDangChay(true)
    setTab('nhat-ky')
    setTrangThai('đang chạy…')
    ghi(`▶ Bắt đầu — nhấn ${r.value?.hotkey ?? 'F6'} để dừng bất cứ lúc nào`, 'ok')
  }, [nodes, ten, startDelay, ghi])

  const dung = useCallback(async () => {
    await py.stop()
    setTrangThai('đang dừng…')
  }, [])

  /** Ctrl+C: chép các khối đang chọn + những đường nối NẰM GIỮA chúng. */
  const chepKhoi = useCallback(() => {
    if (!dangChon.length) return
    const idChon = new Set(dangChon.map(n => n.id))
    boNhoKhoi = {
      // Lấy `pos` từ VỊ TRÍ THẬT của node lúc này, không lấy `step.pos` trong data:
      // kéo khối chỉ đổi `node.position`, còn `step.pos` mãi tới lúc lưu/soát mới được
      // ghi lại. Chép sau khi kéo mà dùng `step.pos` là lấy nhầm chỗ cũ, và cụm dán ra
      // sẽ méo hình so với cụm gốc.
      steps: dangChon.map(n => ({
        ...JSON.parse(JSON.stringify((n.data as { step: Step }).step)),
        pos: [Math.round(n.position.x), Math.round(n.position.y)] as [number, number],
      })),
      edges: rf_sang_edges(edges).filter(e => idChon.has(e.from) && idChon.has(e.to)),
    }
    ghi(`đã chép ${dangChon.length} khối`)
  }, [dangChon, edges, ghi])

  /** Ctrl+V: dán ra bản sao có id MỚI, đặt NGAY CHỖ CON TRỎ, nối lại y như bản gốc.
   *
   *  Trước đây dán ra cách bản gốc 40px. Nghe thì hợp lý nhưng dùng mới thấy dở: chép
   *  một khối ở đầu sơ đồ rồi cuộn sang cuối để dán, bản sao nằm cạnh BẢN GỐC — tức là
   *  ngoài màn hình, và người dùng tưởng lệnh dán không ăn. */
  const danKhoi = useCallback(async () => {
    if (!boNhoKhoi.steps.length) return
    const r = await py.clone_steps(boNhoKhoi.steps)
    if (!r.ok || !r.value) { ghi('không dán được: ' + r.error, 'err'); return }
    const { steps: moi, map, cards } = r.value
    chup()
    // Dời cả CỤM cho góc trên-trái của nó rơi vào con trỏ, giữ nguyên khoảng cách
    // tương đối giữa các khối — dán 3 khối đang nối thành chuỗi mà mỗi cái văng một
    // nơi thì coi như phải xếp lại từ đầu.
    const goc = diemDan()
    const x0 = Math.min(...moi.map(s => s.pos?.[0] ?? 80))
    const y0 = Math.min(...moi.map(s => s.pos?.[1] ?? 120))
    const dx = goc ? Math.round(goc.x - x0) : 40
    const dy = goc ? Math.round(goc.y - y0) : 40
    setNodes(ds => [...ds.map(k => ({ ...k, selected: false })), ...moi.map((st, i) => {
      const p: [number, number] = [(st.pos?.[0] ?? 80) + dx, (st.pos?.[1] ?? 120) + dy]
      return {
        id: st.id, type: 'buoc',
        position: { x: p[0], y: p[1] },
        data: { step: { ...st, pos: p }, card: cards[i] },
        selected: true,
      }
    })])
    // Nối lại theo bảng tra id cũ→mới. Không remap là đường nối trỏ về bản GỐC.
    setEdges(e => [...e, ...boNhoKhoi.edges
      .filter(x => map[x.from] && map[x.to])
      .map(x => ({
        id: `${map[x.from]}->${map[x.to]}:${Date.now()}${Math.round(performance.now())}`,
        source: map[x.from], target: map[x.to],
        sourceHandle: (x as { from_side?: string }).from_side ?? 'right',
        targetHandle: (x as { to_side?: string }).to_side ?? 'left',
        markerEnd: MUI_TEN,
      }))])
    ghi(`đã dán ${moi.length} khối`)
  }, [chup, setNodes, setEdges, ghi, diemDan])

  const luu = useCallback(async () => {
    const t = window.prompt('Lưu Process với tên:', ten)
    if (!t) return
    const r = await py.save_process(t, rf_sang_steps(nodes), rf_sang_edges(edges), startDelay)
    if (r.ok) { setTen(t); ghi(`đã lưu template "${t}"`); setTrangThai('đã lưu') }
    else ghi('lưu hỏng: ' + r.error)
  }, [ten, nodes, edges, startDelay, ghi])

  const moProcess = useCallback(async (t: string) => {
    const r = await py.load_process(t)
    if (!r.ok || !r.value) { ghi('mở hỏng: ' + r.error, 'err'); return }
    chup()
    const { nodes: n, edges: e } = doc_sang_rf(r.value)
    setNodes(n); setEdges(e); setTen(r.value.name); setStartDelay(r.value.start_delay)
    ghi(`mở template "${t}"`)
    setTimeout(() => fitView({ padding: 0.2, duration: 300 }), 40)
  }, [chup, setNodes, setEdges, ghi, fitView])

  /** Chèn 1 Loop/Nhóm có sẵn vào Process đang mở — KHÔNG thay cả Process. */
  const chenBuoc = useCallback(async (kind: 'loop' | 'group', t: string) => {
    const r = await py.insert_step_template(kind, t)
    if (!r.ok || !r.value) { ghi('chèn hỏng: ' + r.error, 'err'); return }
    chup()
    const { step, card } = r.value
    const x = nodes.length ? Math.max(...nodes.map(n => n.position.x)) + 420 : 80
    setNodes(n => [...n.map(k => ({ ...k, selected: false })),
      { id: step.id, type: 'buoc', position: { x, y: 120 }, data: { step, card }, selected: true }])
    ghi(`chèn ${kind === 'loop' ? 'Loop' : 'Nhóm'} "${t}"`)
  }, [nodes, chup, setNodes, ghi])

  /** Lưu riêng bước đang chọn thành template Loop/Nhóm dùng lại được. */
  const luuBuoc = useCallback(async (kind: 'loop' | 'group') => {
    const n = dangChon[0]
    if (!n) return
    const st = (n.data as { step: Step }).step
    const t = window.prompt(`Lưu ${kind === 'loop' ? 'Loop' : 'Nhóm'} với tên:`,
                            String(st.name ?? ''))
    if (!t) return
    const r = await py.save_step_template(kind, t, st)
    ghi(r.ok ? `đã lưu template ${kind} "${t}"` : 'lưu hỏng: ' + r.error, r.ok ? 'ok' : 'err')
  }, [dangChon, ghi])

  /** Đặt khối đang chọn làm bước CHẠY ĐẦU TIÊN.
   *
   *  `flow_entry` lấy bước đầu tiên trong danh sách mà KHÔNG có đường nối đi vào.
   *  Nên phải làm cả hai: gỡ mọi đường nối đi vào nó, và đưa nó lên đầu danh sách.
   *  Chỉ làm một trong hai thì bấm xong không thấy gì đổi — kiểu khó chịu nhất. */
  const datBatDau = useCallback(() => {
    const n = dangChon[0]
    if (!n) return
    chup()
    setEdges(e => e.filter(k => k.target !== n.id))
    setNodes(ds => [n, ...ds.filter(k => k.id !== n.id)])
    ghi(`đặt "${(n.data as { card: Card }).card.title}" làm bước bắt đầu`, 'ok')
  }, [dangChon, chup, setNodes, setEdges, ghi])

  /** Mở Process từ file BẤT KỲ (ngoài thư mục templates/). */
  const moFile = useCallback(async () => {
    const r = await py.open_process_file()
    if (!r.ok) { if (r.error) ghi('mở hỏng: ' + r.error, 'err'); return }
    chup()
    const { nodes: n, edges: e } = doc_sang_rf(r.value!)
    setNodes(n); setEdges(e); setTen(r.value!.name); setStartDelay(r.value!.start_delay)
    ghi('mở Process từ file ngoài')
    setTimeout(() => fitView({ padding: 0.2, duration: 300 }), 40)
  }, [chup, setNodes, setEdges, ghi, fitView])

  const luuRaFile = useCallback(async () => {
    const r = await py.save_process_file(ten, rf_sang_steps(nodes), rf_sang_edges(edges), startDelay)
    if (r.ok) ghi(`đã lưu ra ${r.value?.path}`, 'ok')
    else if (r.error) ghi('lưu hỏng: ' + r.error, 'err')
  }, [ten, nodes, edges, startDelay, ghi])

  const chenTuFile = useCallback(async (kind: 'loop' | 'group') => {
    const r = await py.insert_step_file(kind)
    if (!r.ok) { if (r.error) ghi('chèn hỏng: ' + r.error, 'err'); return }
    chup()
    const { step, card } = r.value!
    const x = nodes.length ? Math.max(...nodes.map(n => n.position.x)) + 420 : 80
    setNodes(n => [...n.map(k => ({ ...k, selected: false })),
      { id: step.id, type: 'buoc', position: { x, y: 120 }, data: { step, card }, selected: true }])
    ghi(`chèn ${kind} từ file ngoài`)
  }, [nodes, chup, setNodes, ghi])

  /** Phủ màn hình, chỉ ra mọi điểm sẽ bị click — soi lại trước khi chạy. */
  const xemDiem = useCallback(async () => {
    const r = await py.review_points(rf_sang_steps(nodes))
    if (!r.ok) ghi(r.error ?? 'không xem được', 'warn')
  }, [nodes, ghi])

  const noi = useCallback((c: Connection) => {
    if (c.source === c.target) return          // tự nối vào chính mình thì vô nghĩa
    chup()
    setEdges(e => addEdge({
      ...c, id: `${c.source}->${c.target}:${Date.now()}`,
      markerEnd: MUI_TEN,
    }, e))
  }, [chup, setEdges])

  /** Double-click lên dây = huỷ kết nối.
   *
   *  Cùng một quy ước với khối: nhấp đúp lên thứ gì thì tác động lên chính thứ đó
   *  (khối -> mở sửa, dây -> bỏ dây). Dây chỉ vẽ dày 1.8px nhưng React Flow phủ sẵn
   *  một đường bắt chuột rộng 20px nên không cần nhắm chính xác.
   *
   *  Có `chup()` nên lỡ tay thì Ctrl+Z lấy lại được. */
  const huyNoi = useCallback((ev: React.MouseEvent, d: Edge) => {
    ev.stopPropagation()
    chup()
    setEdges(e => e.filter(k => k.id !== d.id))
    ghi('đã huỷ 1 kết nối (Ctrl+Z để lấy lại)')
  }, [chup, setEdges, ghi])

  /* ------------------------------ phím tắt ------------------------------- */
  useEffect(() => {
    const f = (ev: KeyboardEvent) => {
      const o = ev.target as HTMLElement
      if (o && (o.tagName === 'INPUT' || o.tagName === 'TEXTAREA')) return
      // Hộp thoại đang mở thì phím tắt của canvas PHẢI im: nếu không, bấm Delete
      // trong hộp thoại vừa xoá hành động vừa xoá luôn cả khối phía sau.
      if (document.querySelector('.lop-phu')) return
      const ctrl = ev.ctrlKey || ev.metaKey
      if (ctrl && ev.key.toLowerCase() === 'z' && !ev.shiftKey) { ev.preventDefault(); hoanTac() }
      else if (ctrl && (ev.key.toLowerCase() === 'y' || (ev.shiftKey && ev.key.toLowerCase() === 'z'))) { ev.preventDefault(); lamLai() }
      else if (ctrl && ev.key.toLowerCase() === 'd') { ev.preventDefault(); nhanBan() }
      else if (ctrl && ev.key.toLowerCase() === 'c') { ev.preventDefault(); chepKhoi() }
      else if (ctrl && ev.key.toLowerCase() === 'v') { ev.preventDefault(); danKhoi() }
      else if (ctrl && ev.key.toLowerCase() === 's') { ev.preventDefault(); luu() }
      else if (ev.key === 'Delete') { ev.preventDefault(); xoa() }
      else if (ev.key === 'F2') { ev.preventDefault(); doiTen() }
    }
    window.addEventListener('keydown', f)
    return () => window.removeEventListener('keydown', f)
  }, [hoanTac, lamLai, nhanBan, luu, xoa, doiTen, chepKhoi, danKhoi])

  /* Kéo hộp: chụp ảnh MỘT lần lúc bắt đầu kéo, không phải mỗi frame — nếu không thì
     một cú kéo tạo ra 60 bước undo và Ctrl+Z thành vô dụng. */
  const dangKeo = useRef(false)
  const batDauKeo = useCallback(() => { if (!dangKeo.current) { dangKeo.current = true; chup() } }, [chup])
  const ketThucKeo = useCallback(() => { dangKeo.current = false }, [])

  /* Gắn số thứ tự vào node ngay trước khi vẽ. Không nhét vào state `nodes` để
     đừng làm bẩn dữ liệu bước — số thứ tự là thứ TÍNH RA, không phải thuộc tính. */
  const nodesCoSo = useMemo(
    () => nodes.map(n => ({ ...n, data: { ...(n.data as object), thuTu: thuTu[n.id] } })),
    [nodes, thuTu])

  const buocChon = dangChon[0] ? (dangChon[0].data as { step: Step }).step : null
  const laLoop = buocChon?.kind === 'loop'
  const laNhom = buocChon?.kind === 'group'

  const mucLuu: MucMenu[] = [
    { nhan: 'Đổi tên Process…', chay: doiTenProcess },
    { nhan: 'Lưu cả Process thành template', chay: luu },
    { nhan: 'Lưu riêng Loop đang chọn', chay: () => luuBuoc('loop'),
      tat: !laLoop, lyDo: 'chọn một Action_Loop trước' },
    { nhan: 'Lưu riêng Nhóm đang chọn', chay: () => luuBuoc('group'),
      tat: !laNhom, lyDo: 'chọn một Nhóm HĐ 1 lần trước' },
    { nhan: 'Lưu ra file khác…', chay: luuRaFile },
  ]
  const mucMo: MucMenu[] = [
    { nhan: 'Mở Process (thay toàn bộ)',
      chay: () => setMoPicker({ kind: 'process', tieuDe: 'Mở Process', xong: t => { setMoPicker(null); moProcess(t) } }) },
    { nhan: 'Chèn Loop có sẵn vào Process này',
      chay: () => setMoPicker({ kind: 'loop', tieuDe: 'Chèn Action_Loop', xong: t => { setMoPicker(null); chenBuoc('loop', t) } }) },
    { nhan: 'Chèn Nhóm có sẵn vào Process này',
      chay: () => setMoPicker({ kind: 'group', tieuDe: 'Chèn Nhóm HĐ 1 lần', xong: t => { setMoPicker(null); chenBuoc('group', t) } }) },
    { nhan: 'Mở từ file khác…', chay: moFile },
  ]

  const soLoi = vanDe.filter(v => v.severity === 'error').length
  const soCanhBao = vanDe.length - soLoi

  return (
    <div className="khung">
      <Ribbon
        themLoop={() => themKhoi('loop')}
        themNhom={() => themKhoi('group')}
        themHanhDong={() => themKhoi('action')}
        themReNhanh={() => themKhoi('action', 'confirm_mod')}
        sua={() => dangChon[0] && setDangSua(dangChon[0].id)} datBatDau={datBatDau}
        nhanBan={nhanBan} xoa={xoa}
        hoanTac={hoanTac} lamLai={lamLai}
        mucLuu={mucLuu} mucMo={mucMo} xemDiem={xemDiem}
        ten={ten} datTen={setTen}
        startDelay={startDelay} datStartDelay={setStartDelay}
        chay={() => chay()} dung={dung} dangChay={dangChay}
        coChon={dangChon.length > 0}
        coTheHoanTac={coLui} coTheLamLai={coToi}
      />

      <div className={'vung-canvas' + (dangNoi ? ' dang-noi' : '')}>
        <ReactFlow
          nodes={nodesCoSo} edges={edges}
          onNodesChange={onNodesChange as (c: NodeChange[]) => void}
          onEdgesChange={onEdgesChange as (c: EdgeChange[]) => void}
          onConnect={noi}
          onConnectStart={() => setDangNoi(true)}
          onConnectEnd={() => setDangNoi(false)}
          onNodeDragStart={batDauKeo}
          onNodeDragStop={ketThucKeo}
          onNodeDoubleClick={(_, n) => setDangSua(n.id)}
          onEdgeDoubleClick={huyNoi}
          nodeTypes={nodeTypes}
          connectionMode={ConnectionMode.Loose}
          proOptions={{ hideAttribution: true }}
          minZoom={0.25} maxZoom={2}
          defaultEdgeOptions={KIEU_DUONG_NOI}
          deleteKeyCode={null}
          multiSelectionKeyCode={PHIM_CHON_NHIEU}
          fitView
        >
          <Background variant={BackgroundVariant.Dots} gap={22} size={1.4} color="var(--canvas-dot)" />
        </ReactFlow>

        {nodes.length === 0 && sanSang && (
          <div className="trong-rong">
            <div className="to">Canvas trống</div>
            <div>Bấm <b>Loop</b> / <b>Nhóm</b> / <b>HĐ lẻ</b> ở thanh trên để thêm khối, rồi kéo từ cổng bên cạnh hộp để nối.</div>
          </div>
        )}
      </div>

      <div className={'bang-duoi' + (panelGap ? ' thu-gon' : '')}
           style={{ height: panelGap ? CAO_GAP : panelCao }}>
        <div className="thanh-keo" onMouseDown={batDauKeoPanel}
             title="Kéo để chỉnh chiều cao" />
        <div className="hang-tab" onDoubleClick={() => setPanelGap(v => !v)}>
          <button className={'tab' + (tab === 'van-de' ? ' dang' : '')}
                  onClick={() => { setTab('van-de'); setPanelGap(false) }}>
            Vấn đề{vanDe.length ? ` (${vanDe.length})` : ''}
          </button>
          <button className={'tab' + (tab === 'nhat-ky' ? ' dang' : '')}
                  onClick={() => { setTab('nhat-ky'); setPanelGap(false) }}>
            Nhật ký
          </button>
          <span className="day" />
          {tab === 'nhat-ky' && !panelGap &&
            <button className="nut-nho" onClick={() => setNhatKy([])}>Xoá nhật ký</button>}
          <button className="nut-nho nut-gap" onClick={() => setPanelGap(v => !v)}
                  title={panelGap ? 'Mở bảng (hoặc double-click hàng tab)'
                                  : 'Gập bảng xuống (hoặc double-click hàng tab)'}>
            {panelGap ? '▲' : '▼'}
          </button>
        </div>
        {!panelGap && <div className="noi-dung-tab">
          {tab === 'van-de' ? (
            vanDe.length === 0
              ? <div className="trong">Không có vấn đề nào.</div>
              : vanDe.map((v, i) => (
                <div key={i}
                     className={'dong-van-de ' + (v.severity === 'error' ? 'loi' : 'canh-bao')}
                     title="Bấm để chọn khối bị lỗi"
                     onClick={() => {
                       // `step` có thể là CHỈ SỐ (lỗi trong bước) hoặc ID (lỗi đồ thị)
                       const id = typeof v.step === 'number'
                         ? nodes[v.step]?.id
                         : (v.step as unknown as string)
                       if (!id) return
                       setNodes(ds => ds.map(k => ({ ...k, selected: k.id === id })))
                       const n = nodes.find(k => k.id === id)
                       if (n) setCenter(n.position.x + 148, n.position.y + 90,
                                        { zoom: mucZoom, duration: 350 })
                     }}>
                  <span className="muc">{v.severity === 'error' ? '●' : '▲'}</span>
                  <span>{v.message}</span>
                </div>
              ))
          ) : (
            nhatKy.length === 0
              ? <div className="trong">Chưa có gì.</div>
              : <div className="nhat-ky">
                  {nhatKy.map((l, i) => (
                    <div key={i} className={'dong-log' + (l.tag ? ' t-' + l.tag : '')}>
                      <span className="gio">{l.gio}</span>{l.msg}
                    </div>
                  ))}
                  <div ref={cuoiLog} />
                </div>
          )}
        </div>}
      </div>

      <div className="thanh-trang-thai">
        {/* ⚙ nằm ở góc trái dưới cùng — chỗ quen thuộc cho cài đặt (VSCode cũng vậy),
            và nó là thứ app-wide nên không thuộc về cụm chạy của Process. */}
        <button className="nut-tt" onClick={() => setMoCaiDat(true)} title="Cài đặt">
          {/* Bánh răng: vành ngoài + lỗ giữa + 8 RĂNG NGẮN VÀ DÀY. Bản đầu chỉ có
              tâm nhỏ với 8 tia dài mảnh nên nhìn ra mặt trời chứ không ra bánh răng. */}
          <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor"
               strokeLinecap="round" strokeLinejoin="round">
            <circle cx="8" cy="8" r="4.9" strokeWidth="1.3" />
            <circle cx="8" cy="8" r="1.9" strokeWidth="1.3" />
            <g strokeWidth="2">
              <path d="M8 1.3v1.4M8 13.3v1.4M14.7 8h-1.4M2.7 8H1.3" />
              <path d="M12.7 3.3l-1 1M4.3 11.7l-1 1M12.7 12.7l-1-1M4.3 4.3l-1-1" />
            </g>
          </svg>
        </button>
        <span><span className="so">{nodes.length}</span> khối</span>
        <span><span className="so">{edges.length}</span> đường nối</span>
        {soLoi > 0 && <span style={{ color: 'var(--err)' }}>{soLoi} lỗi</span>}
        {soCanhBao > 0 && <span style={{ color: 'var(--warn)' }}>{soCanhBao} cảnh báo</span>}
        {coVong && <span style={{ color: 'var(--warn)' }}>đường nối tạo vòng lặp</span>}
        {dangChay && <span className="dang-chay">● đang chạy — {phimDung} để dừng</span>}
        <span className="day" />
        <span>{trangThai}</span>
        {/* Ba nút thu phóng. Trước đây là cụm DỌC của React Flow nổi trên canvas —
            nó che mất góc dưới-trái và trùng chức năng với thanh này. Gom về đây,
            xếp ngang, ngay cạnh con số phần trăm mà chúng điều khiển. */}
        <div className="cum-zoom">
          <button className="nut-zoom" onClick={() => zoomOut()} title="Thu nhỏ">−</button>
          <button className="nut-zoom" onClick={() => zoomIn()} title="Phóng to">+</button>
          <button className="nut-zoom" title="Vừa khung — thu phóng cho vừa toàn bộ sơ đồ"
                  onClick={() => fitView({ padding: 0.2, duration: 300 })}>
            <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor"
                 strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2.5 5.5v-3h3M13.5 5.5v-3h-3M2.5 10.5v3h3M13.5 10.5v3h-3" />
            </svg>
          </button>
        </div>
        <span className="so">{Math.round(mucZoom * 100)}%</span>
      </div>

      {moCaiDat && boot && (
        <SettingsDialog boot={boot} doiMauNgay={doiMauNgay}
                        onDong={() => setMoCaiDat(false)}
                        onLuu={s2 => {
                          setBoot(b => (b ? { ...b, settings: s2 } : b))
                          setMoCaiDat(false)
                          ghi('đã lưu cài đặt', 'ok')
                        }} />
      )}

      {moPicker && (
        <TemplatePicker kind={moPicker.kind} tieuDe={moPicker.tieuDe}
                        onChon={moPicker.xong} onDong={() => setMoPicker(null)}
                        onDuyetFile={() => {
                          const k = moPicker.kind
                          setMoPicker(null)
                          if (k === 'process') moFile(); else chenTuFile(k)
                        }} />
      )}

      {dangSua && boot && (() => {
        const n = nodes.find(k => k.id === dangSua)
        if (!n) return null
        const st = (n.data as { step: Step }).step
        // HĐ lẻ chính LÀ một hành động -> mở thẳng hộp thoại hành động, khỏi bắt
        // người dùng đi qua một lớp "danh sách 1 phần tử" vô nghĩa.
        return st.kind === 'action'
          ? <ActionDialog action={st as Record<string, any>} boot={boot} mods={mods}
                          onDong={() => setDangSua(null)}
                          onLuu={a => ghiBuoc({ ...a, kind: 'action', id: st.id, pos: st.pos } as Step)} />
          : <StepDialog step={st} boot={boot} mods={mods}
                        onDong={() => setDangSua(null)} onLuu={ghiBuoc} />
      })()}
    </div>
  )
}

export default function App() {
  return <ReactFlowProvider><Ung /></ReactFlowProvider>
}
