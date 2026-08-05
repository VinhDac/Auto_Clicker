/** Hình dạng dữ liệu đi qua cầu nối. Phải khớp với `api.py` / `core.py`.
 *
 * Lưu ý: phía JS KHÔNG tự dựng mấy shape này từ con số 0 — nó nhận từ Python và gửi
 * lại nguyên vẹn. Mọi hiểu biết về định dạng file nằm ở `core.py`.
 */

export type StepKind = 'loop' | 'group' | 'action'

/** Một bước — coi như hộp đen. JS chỉ đụng tới `id`, `kind`, `name`, `pos`. */
export interface Step {
  id: string
  kind: StepKind
  name?: string
  pos?: [number, number]
  actions?: unknown[]
  [k: string]: unknown
}

export interface ProcEdge {
  from: string
  to: string
  port: string
}

/** Nội dung vẽ lên hộp — do `api.describe()` sinh, không phải JS tự ghép. */
export interface CardLine {
  text: string
  /** Loại hành động — giao diện dùng để CHỌN ICON. Python không gắn emoji vào text nữa. */
  type?: string | null
  /** Nằm TRƯỚC dấu "Loop từ đây" -> chạy đúng 1 lần lúc đầu. */
  prologue: boolean
  /** check_mod / abyss — thứ có thể kết thúc Loop. */
  goal: boolean
}

export interface Card {
  id: string
  kind: StepKind
  title: string
  badges: string[]
  lines: CardLine[]
  so_hanh_dong: number
  co_muc_tieu: boolean
}

export interface Problem {
  severity: 'error' | 'warning' | string
  message: string
  step?: number | null
  index?: number | null
}

export interface ProcessDoc {
  name: string
  start_delay: number
  steps: Step[]
  edges: ProcEdge[]
  cards: Card[]
  note?: string | null
}

export interface Bootstrap {
  settings: Record<string, unknown>
  action_types: string[]
  action_labels: Record<string, string>
  template_kinds: string[]
  goal_types: string[]
  point_types: string[]
  mod_keys: string[]
  hybrid_labels: Record<string, string>
  abyss_max_rerolls: number
  games: Record<string, string>
  accent_presets: Record<string, string>
  default_max_loops: number
  screen: [number, number, number, number]
  has_clip: boolean
  has_screen: boolean
  has_ocr: boolean
  ocr_reason: string | null
  app_dir: string
}

/** Một dòng nhật ký do Python đẩy sang trong lúc chạy. */
export interface DongLog {
  msg: string
  tag?: string | null
  /** Dòng cuối cùng của lần chạy — kèm tổng số vòng. */
  het?: boolean
  so_vong?: number
}

export interface Reply<T> {
  ok: boolean
  value?: T
  error?: string
  trace?: string
  [k: string]: unknown
}
