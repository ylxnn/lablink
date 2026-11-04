export type User = {
  id: string;
  email: string;
  full_name: string;
  role: "admin" | "manager" | "member";
  team_id: string;
  is_active: boolean;
  bio?: string;
  phone?: string;
  student_id?: string;
};
export type Equipment = {
  id: string;
  name: string;
  code: string;
  team_id: string;
  category: string;
  location: string;
  description: string;
  status: string;
  approval_required: boolean;
};
export type Booking = {
  id: string;
  equipment_id: string;
  equipment_name?: string;
  user_name?: string;
  user_id: string;
  starts_at: string;
  ends_at: string;
  purpose: string;
  status: string;
  decision_note: string;
  created_at: string;
};
export type Fault = {
  id: string;
  equipment_id: string;
  equipment_name: string;
  description: string;
  status: string;
  resolution: string;
  created_at: string;
};
export type Notice = {
  id: string;
  title: string;
  body: string;
  read_at: string | null;
  created_at: string;
};
export type Audit = {
  id: string;
  action: string;
  target_id: string;
  actor_id: string;
  team_id: string;
  detail: string;
  created_at: string;
};
export type Page<T> = { items: T[]; total: number };

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch("/api/v1" + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization:
        "Bearer " + (sessionStorage.getItem("lablink-token") || ""),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: "请求失败，请检查网络" }));
    const message = Array.isArray(data.detail)
      ? data.detail.map((x: { msg: string }) => x.msg).join("；")
      : data.detail;
    if (response.status === 401 && path !== "/auth/login") {
      sessionStorage.removeItem("lablink-token");
      window.dispatchEvent(new Event("lablink-logout"));
    }
    throw new Error(message || `请求失败 (${response.status})`);
  }
  return response.json();
}
export const post = (body: unknown) => ({
  method: "POST",
  body: JSON.stringify(body),
});
export const date = (value: string) =>
  new Date(/[Z+]\d*:?\d*$/.test(value) ? value : value + "Z").toLocaleString(
    "zh-CN",
    {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    },
  );
export const label: Record<string, string> = {
  available: "可预约",
  maintenance: "维护中",
  retired: "已停用",
  pending: "待审批",
  approved: "已通过",
  checked_out: "使用中",
  returned: "已归还",
  cancelled: "已取消",
  rejected: "未通过",
  expired: "审批过期",
  no_show: "未领用",
  open: "待处理",
  resolved: "已修复",
  admin: "平台管理员",
  manager: "设备管理员",
  member: "实验室成员",
  vision: "视觉智能实验室",
  robotics: "机器人实验室",
  delivered: "已送达",
  dead: "待重试",
  skipped: "已跳过",
};
