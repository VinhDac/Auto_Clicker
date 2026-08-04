import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ReactFlow, Background, BackgroundVariant, Controls, ConnectionMode,
  useNodesState, useEdgesState, addEdge, useReactFlow, ReactFlowProvider, MarkerType,
  type Node, type Edge, type Connection, type NodeChange, type EdgeChange,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { py, cho_cau_noi } from './api'
import type { Bootstrap, Card, ProcEdge, Problem, ProcessDoc, Step, StepKind } from './types'
import Ribbon from './components/Ribbon'
import StepNode from './components/StepNode'
import StepDialog from './components/StepDialog'
import ActionDialog from './components/ActionDialog'

const nodeTypes = { buoc: StepNode }

const MUI_TEN = { type: MarkerType.ArrowClosed, width: 16, height: 16, color: '#6a6a6a' }

/** 'default' = đường bezier. Cố ý KHÔNG dùng 'smoothstep': hộp cao thấp khác nhau nên
 *  hai đầu nối hiếm khi cùng độ cao, đường bậc thang gãy khúc trông như lỗi vẽ. */
const KIEU_DUONG_NOI = { type: 'default', animated: false, markerEnd: MUI_TEN }

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
  const { fitView, zoomIn, zoomOut, getZoom } = useReactFlow()

  const lui = useRef<Anh[]>([])
  const toi = useRef<Anh[]>([])
  const cuoiLog = useRef<HTMLDivElement>(null)
  const [coLui, setCoLui] = useState(false)
  const [coToi, setCoToi] = useState(false)

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
      const r = await py.validate(rf_sang_steps(nodes))
      if (r.ok) setVanDe(r.value ?? [])
    }, 250)   // gộp lại: kéo hộp bắn ra hàng chục thay đổi mỗi giây
    return () => clearTimeout(h)
  }, [nodes, sanSang])

  /* Nhật ký tự cuộn xuống đáy — đang chạy mà phải cuộn tay thì không theo dõi nổi. */
  useEffect(() => {
    if (tab === 'nhat-ky') cuoiLog.current?.scrollIntoView({ block: 'end' })
  }, [nhatKy, tab])

  /* ------------------------------ thao tác ------------------------------- */
  const dangChon = useMemo(() => nodes.filter(n => n.selected), [nodes])

  const themKhoi = useCallback(async (kind: StepKind) => {
    const r = await py.new_step(kind)
    if (!r.ok || !r.value) { ghi('không tạo được khối: ' + r.error); return }
    chup()
    const { step, card } = r.value
    const x = nodes.length ? Math.max(...nodes.map(n => n.position.x)) + 420 : 80
    const y = nodes.length ? nodes[nodes.length - 1].position.y : 120
    const moi: Node = { id: step.id, type: 'buoc', position: { x, y }, data: { step, card } }
    setNodes(n => [...n.map(k => ({ ...k, selected: false })), { ...moi, selected: true }])
    ghi(`thêm khối ${card.title}`)
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
    chup()
    const id = 'c' + Math.random().toString(16).slice(2, 10)
    const step: Step = { ...JSON.parse(JSON.stringify(d.step)), id }
    const card: Card = { ...d.card, id, title: d.card.title + ' (bản sao)' }
    step.name = card.title
    setNodes(ds => [...ds.map(k => ({ ...k, selected: false })), {
      id, type: 'buoc', position: { x: n.position.x + 40, y: n.position.y + 60 },
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

  const luu = useCallback(async () => {
    const t = window.prompt('Lưu Process với tên:', ten)
    if (!t) return
    const r = await py.save_process(t, rf_sang_steps(nodes), rf_sang_edges(edges), startDelay)
    if (r.ok) { setTen(t); ghi(`đã lưu template "${t}"`); setTrangThai('đã lưu') }
    else ghi('lưu hỏng: ' + r.error)
  }, [ten, nodes, edges, startDelay, ghi])

  const mo = useCallback(async () => {
    const ds = await py.list_templates('process')
    if (!ds.ok || !ds.value?.length) { ghi('chưa có template Process nào'); return }
    const t = window.prompt('Mở template nào?\n\n' + ds.value.join('\n'), ds.value[0])
    if (!t) return
    const r = await py.load_process(t)
    if (!r.ok || !r.value) { ghi('mở hỏng: ' + r.error); return }
    chup()
    const { nodes: n, edges: e } = doc_sang_rf(r.value)
    setNodes(n); setEdges(e); setTen(r.value.name); setStartDelay(r.value.start_delay)
    ghi(`mở template "${t}"`)
    setTimeout(() => fitView({ padding: 0.2, duration: 300 }), 40)
  }, [chup, setNodes, setEdges, ghi, fitView])

  const noi = useCallback((c: Connection) => {
    if (c.source === c.target) return          // tự nối vào chính mình thì vô nghĩa
    chup()
    setEdges(e => addEdge({
      ...c, id: `${c.source}->${c.target}:${Date.now()}`,
      markerEnd: MUI_TEN,
    }, e))
  }, [chup, setEdges])

  /* ------------------------------ phím tắt ------------------------------- */
  useEffect(() => {
    const f = (ev: KeyboardEvent) => {
      const o = ev.target as HTMLElement
      if (o && (o.tagName === 'INPUT' || o.tagName === 'TEXTAREA')) return
      const ctrl = ev.ctrlKey || ev.metaKey
      if (ctrl && ev.key.toLowerCase() === 'z' && !ev.shiftKey) { ev.preventDefault(); hoanTac() }
      else if (ctrl && (ev.key.toLowerCase() === 'y' || (ev.shiftKey && ev.key.toLowerCase() === 'z'))) { ev.preventDefault(); lamLai() }
      else if (ctrl && ev.key.toLowerCase() === 'd') { ev.preventDefault(); nhanBan() }
      else if (ctrl && ev.key.toLowerCase() === 's') { ev.preventDefault(); luu() }
      else if (ev.key === 'Delete') { ev.preventDefault(); xoa() }
      else if (ev.key === 'F2') { ev.preventDefault(); doiTen() }
    }
    window.addEventListener('keydown', f)
    return () => window.removeEventListener('keydown', f)
  }, [hoanTac, lamLai, nhanBan, luu, xoa, doiTen])

  /* Kéo hộp: chụp ảnh MỘT lần lúc bắt đầu kéo, không phải mỗi frame — nếu không thì
     một cú kéo tạo ra 60 bước undo và Ctrl+Z thành vô dụng. */
  const dangKeo = useRef(false)
  const batDauKeo = useCallback(() => { if (!dangKeo.current) { dangKeo.current = true; chup() } }, [chup])
  const ketThucKeo = useCallback(() => { dangKeo.current = false }, [])

  const soLoi = vanDe.filter(v => v.severity === 'error').length
  const soCanhBao = vanDe.length - soLoi

  return (
    <div className="khung">
      <div className="dau-trang">
        <span className="nhan">Process:</span>
        <input className="o-ten" value={ten} onChange={e => setTen(e.target.value)} spellCheck={false} />
        <span className="nhan">Chờ trước khi chạy:</span>
        <input className="o-ten" style={{ minWidth: 56, width: 56 }} value={startDelay}
               onChange={e => setStartDelay(Math.max(0, parseInt(e.target.value) || 0))} />
        <span className="day" />
        {dangChay && <span className="nhan dang-chay">● đang chạy — {phimDung} để dừng</span>}
        <button className="nut" onClick={dung} disabled={!dangChay}>■ Dừng</button>
        <button className="nut chinh" onClick={() => chay()} disabled={dangChay}>▶ Chạy</button>
      </div>

      <Ribbon
        themLoop={() => themKhoi('loop')}
        themNhom={() => themKhoi('group')}
        themHanhDong={() => themKhoi('action')}
        doiTen={doiTen} nhanBan={nhanBan} xoa={xoa}
        hoanTac={hoanTac} lamLai={lamLai}
        luu={luu} mo={mo}
        vuaManHinh={() => fitView({ padding: 0.2, duration: 300 })}
        coChon={dangChon.length > 0}
        coTheHoanTac={coLui} coTheLamLai={coToi}
      />

      <div className="vung-canvas">
        <ReactFlow
          nodes={nodes} edges={edges}
          onNodesChange={onNodesChange as (c: NodeChange[]) => void}
          onEdgesChange={onEdgesChange as (c: EdgeChange[]) => void}
          onConnect={noi}
          onNodeDragStart={batDauKeo}
          onNodeDragStop={ketThucKeo}
          onNodeDoubleClick={(_, n) => setDangSua(n.id)}
          nodeTypes={nodeTypes}
          connectionMode={ConnectionMode.Loose}
          proOptions={{ hideAttribution: true }}
          minZoom={0.25} maxZoom={2}
          defaultEdgeOptions={KIEU_DUONG_NOI}
          deleteKeyCode={null}
          fitView
        >
          <Background variant={BackgroundVariant.Dots} gap={22} size={1.4} color="var(--canvas-dot)" />
          <Controls showInteractive={false} />
        </ReactFlow>

        {nodes.length === 0 && sanSang && (
          <div className="trong-rong">
            <div className="to">Canvas trống</div>
            <div>Bấm <b>Loop</b> / <b>Nhóm</b> / <b>HĐ lẻ</b> ở thanh trên để thêm khối, rồi kéo từ cổng bên cạnh hộp để nối.</div>
          </div>
        )}
      </div>

      <div className="bang-duoi">
        <div className="hang-tab">
          <button className={'tab' + (tab === 'van-de' ? ' dang' : '')} onClick={() => setTab('van-de')}>
            Vấn đề{vanDe.length ? ` (${vanDe.length})` : ''}
          </button>
          <button className={'tab' + (tab === 'nhat-ky' ? ' dang' : '')} onClick={() => setTab('nhat-ky')}>
            Nhật ký
          </button>
          <span className="day" />
          {tab === 'nhat-ky' && <button className="nut-nho" onClick={() => setNhatKy([])}>Xoá nhật ký</button>}
        </div>
        <div className="noi-dung-tab">
          {tab === 'van-de' ? (
            vanDe.length === 0
              ? <div className="trong">Không có vấn đề nào.</div>
              : vanDe.map((v, i) => (
                <div key={i} className={'dong-van-de ' + (v.severity === 'error' ? 'loi' : 'canh-bao')}>
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
        </div>
      </div>

      <div className="thanh-trang-thai">
        <span><span className="so">{nodes.length}</span> khối</span>
        <span><span className="so">{edges.length}</span> đường nối</span>
        {soLoi > 0 && <span style={{ color: 'var(--err)' }}>{soLoi} lỗi</span>}
        {soCanhBao > 0 && <span style={{ color: 'var(--warn)' }}>{soCanhBao} cảnh báo</span>}
        <span className="day" />
        <span>{trangThai}</span>
        <button className="nut-nho" onClick={() => zoomOut()}>−</button>
        <span className="so">{Math.round(getZoom() * 100)}%</span>
        <button className="nut-nho" onClick={() => zoomIn()}>+</button>
      </div>

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
