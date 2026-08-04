/** Vỏ bọc có kiểu quanh `window.pywebview.api`.
 *
 * Mọi lời gọi Python đi qua đây, không rải `window.pywebview` khắp components —
 * để sau này đổi cách vận chuyển (hoặc giả lập khi test) chỉ phải sửa một file.
 */
import type { Bootstrap, Card, ProcessDoc, Problem, Reply, ProcEdge, Step } from './types'

type PyApi = Record<string, (...a: unknown[]) => Promise<unknown>>

declare global {
  interface Window {
    pywebview?: { api: PyApi }
  }
}

/** Chờ cầu nối sẵn sàng.
 *
 * Cố ý KHÔNG dùng sự kiện 'pywebviewready': nếu nó bắn trước khi bundle chạy xong thì
 * listener gắn sau sẽ không bao giờ nhận được, và app treo ở màn hình trắng.
 */
export function cho_cau_noi(timeout = 10000): Promise<void> {
  const t0 = Date.now()
  return new Promise((ok, hong) => {
    const thu = () => {
      if (window.pywebview?.api) return ok()
      if (Date.now() - t0 > timeout) return hong(new Error('Không kết nối được tới Python'))
      setTimeout(thu, 40)
    }
    thu()
  })
}

async function goi<T>(ten: string, ...args: unknown[]): Promise<Reply<T>> {
  const api = window.pywebview?.api
  if (!api || typeof api[ten] !== 'function') {
    return { ok: false, error: `api.py không có hàm "${ten}"` }
  }
  try {
    return (await api[ten](...args)) as Reply<T>
  } catch (e) {
    return { ok: false, error: String(e) }
  }
}

export const py = {
  bootstrap: () => goi<Bootstrap>('bootstrap'),
  demo_process: () => goi<ProcessDoc>('demo_process'),
  new_process: () => goi<ProcessDoc>('new_process'),
  load_process: (ten: string) => goi<ProcessDoc>('load_process', ten),
  save_process: (ten: string, steps: Step[], edges: ProcEdge[], start_delay: number) =>
    goi<{ path: string; name: string }>('save_process', ten, steps, edges, start_delay),
  list_templates: (kind = 'process') => goi<string[]>('list_templates', kind),
  new_step: (kind: string, actionType = 'left_click') =>
    goi<{ step: Step; card: Card }>('new_step', kind, actionType),
  describe: (steps: Step[]) => goi<Card[]>('describe', steps),
  validate: (steps: Step[]) => goi<Problem[]>('validate', steps),

  // --- hộp thoại hành động ---
  save_action: (draft: Record<string, unknown>) =>
    goi<{ action: Record<string, unknown>; display: string }>('save_action', draft),
  describe_actions: (actions: unknown[]) => goi<string[]>('describe_actions', actions),
  describe_conditions: (conds: unknown[], kind = 'check_mod') =>
    goi<string[]>('describe_conditions', conds, kind),
  action_defaults: (t: string) => goi<Record<string, unknown>>('action_defaults', t),
  get_mods: (game?: string) => goi<string[]>('get_mods', game ?? null),

  // --- 3 overlay chọn trên màn hình (chạy tiến trình con tkinter) ---
  pick_point: () => goi<[number, number]>('pick_point'),
  pick_abyss_frame: (frame?: number[] | null) => goi<number[]>('pick_abyss_frame', frame ?? null),
  pick_inv_grid: (frame?: number[] | null, cells?: number[][] | null) =>
    goi<{ frame: number[]; cells: number[][] }>('pick_inv_grid', frame ?? null, cells ?? null),
}
