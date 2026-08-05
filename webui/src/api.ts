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
  set_title: (ten: string) => goi<null>('set_title', ten),
  demo_process: () => goi<ProcessDoc>('demo_process'),
  new_process: () => goi<ProcessDoc>('new_process'),
  load_process: (ten: string) => goi<ProcessDoc>('load_process', ten),
  save_process: (ten: string, steps: Step[], edges: ProcEdge[], start_delay: number) =>
    goi<{ path: string; name: string }>('save_process', ten, steps, edges, start_delay),
  list_templates: (kind = 'process') => goi<string[]>('list_templates', kind),
  // --- cài đặt ---
  save_settings: (s: Record<string, unknown>) => goi<Record<string, unknown>>('save_settings', s),
  save_ui: (state: Record<string, unknown>) => goi<Record<string, unknown>>('save_ui', state),
  update_mods: (game?: string) => goi<{ game: string; so_luong: number }>('update_mods', game ?? null),

  // --- template Loop / Nhóm ---
  delete_template: (kind: string, ten: string) => goi<null>('delete_template', kind, ten),
  save_step_template: (kind: string, ten: string, step: Step) =>
    goi<{ name: string }>('save_step_template', kind, ten, step),
  insert_step_template: (kind: string, ten: string) =>
    goi<{ step: Step; card: Card }>('insert_step_template', kind, ten),
  review_points: (steps: Step[]) => goi<boolean>('review_points', steps),

  // --- mở / lưu ra file bất kỳ (hộp thoại file native) ---
  open_process_file: () => goi<ProcessDoc>('open_process_file'),
  save_process_file: (ten: string, steps: Step[], edges: ProcEdge[], sd: number) =>
    goi<{ path: string }>('save_process_file', ten, steps, edges, sd),
  insert_step_file: (kind: string) => goi<{ step: Step; card: Card }>('insert_step_file', kind),

  new_step: (kind: string, actionType = 'left_click') =>
    goi<{ step: Step; card: Card }>('new_step', kind, actionType),
  clone_steps: (steps: Step[]) =>
    goi<{ steps: Step[]; map: Record<string, string>; cards: Card[] }>('clone_steps', steps),
  describe: (steps: Step[]) => goi<Card[]>('describe', steps),
  validate: (steps: Step[], edges: ProcEdge[]) => goi<Problem[]>('validate', steps, edges),

  // --- hộp thoại hành động ---
  save_action: (draft: Record<string, unknown>) =>
    goi<{ action: Record<string, unknown>; display: string }>('save_action', draft),
  describe_actions: (actions: unknown[]) =>
    goi<{ text: string; type?: string | null }[]>('describe_actions', actions),
  describe_conditions: (conds: unknown[], kind = 'check_mod') =>
    goi<string[]>('describe_conditions', conds, kind),
  action_defaults: (t: string) => goi<Record<string, unknown>>('action_defaults', t),
  get_mods: (game?: string) => goi<string[]>('get_mods', game ?? null),

  // --- chạy / dừng ---
  run: (name: string, steps: Step[], startDelay: number, boQuaCanhBao = false) =>
    goi<{ hotkey: string }>('run', name, steps, startDelay, boQuaCanhBao),
  stop: () => goi<null>('stop'),

  // --- 3 overlay chọn trên màn hình (chạy tiến trình con tkinter) ---
  pick_point: () => goi<[number, number]>('pick_point'),
  pick_abyss_frame: (frame?: number[] | null) => goi<number[]>('pick_abyss_frame', frame ?? null),
  pick_inv_grid: (frame?: number[] | null, cells?: number[][] | null) =>
    goi<{ frame: number[]; cells: number[][] }>('pick_inv_grid', frame ?? null, cells ?? null),
}
