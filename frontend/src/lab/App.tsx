import {
  useState,
  useEffect,
  useCallback,
  useRef,
  FormEvent,
  ReactNode,
} from "react";
import {
  LayoutDashboard,
  Monitor,
  CalendarDays,
  ClipboardCheck,
  Wrench,
  Bell,
  ShieldCheck,
  Users,
  Activity,
  LogOut,
  ArrowUpRight,
  ArrowRight,
  Plus,
  Search,
  Check,
  ChevronLeft,
  ChevronRight,
  X,
  LoaderCircle,
  MapPin,
  Clock,
  Box,
  FlaskConical,
  RefreshCw,
  Download,
  CheckCircle2,
} from "lucide-react";
import {
  api,
  post,
  date,
  label,
  User,
  Equipment,
  Booking,
  Fault,
  Notice,
  Audit,
  Page,
} from "./api";

type PageName =
  | "overview"
  | "equipment"
  | "bookings"
  | "approvals"
  | "faults"
  | "notifications"
  | "audit"
  | "users"
  | "operations";
type Modal = {
  kind:
    | "reserve"
    | "fault"
    | "device"
    | "action"
    | "resolve"
    | "state"
    | "user"
    | "profile";
  item?: Equipment | Booking | Fault;
  action?: string;
};
type Dashboard = {
  equipment_total: number;
  available: number;
  maintenance: number;
  pending: number;
  active: number;
  completed: number;
  overdue: number;
  recent_bookings: Booking[];
};
const navigation = [
  { id: "overview", name: "空间总览", icon: LayoutDashboard },
  { id: "equipment", name: "设备资源", icon: Monitor },
  { id: "bookings", name: "我的预约", icon: CalendarDays },
  { id: "approvals", name: "预约审批", icon: ClipboardCheck, staff: true },
  { id: "faults", name: "故障与维护", icon: Wrench },
  { id: "notifications", name: "消息中心", icon: Bell },
  { id: "audit", name: "操作审计", icon: ShieldCheck, staff: true },
  { id: "users", name: "成员管理", icon: Users, staff: true },
  { id: "operations", name: "通知队列", icon: Activity, admin: true },
] as const;
const titles: Record<PageName, [string, string]> = {
  overview: ["空间总览", "查看设备，安排今天的实验。"],
  equipment: ["设备资源", "搜索设备、查看空闲时段，再提交预约。"],
  bookings: ["我的预约", "查看审批进度，按时领用和归还。"],
  approvals: ["预约审批", "查看用途、核对时段，让共享更有秩序。"],
  faults: ["故障与维护", "让问题被看见，让设备尽快回到工作状态。"],
  notifications: ["消息中心", "预约进展、使用提醒与维护通知。"],
  audit: ["操作审计", "每一次关键变更，都有迹可循。"],
  users: ["成员管理", "明确职责，共享资源。"],
  operations: ["通知队列", "业务变更与站内通知，可靠地连接起来。"],
};
const localTime = (hours = 1) => {
  const d = new Date(Date.now() + hours * 3600000);
  d.setMinutes(0, 0, 0);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
};

function Badge({ status }: { status: string }) {
  return (
    <span className={"badge " + status}>
      <i />
      {label[status] || status}
    </span>
  );
}
function Empty({
  title = "暂时没有记录",
  text = "新的记录会出现在这里。",
  action,
}: {
  title?: string;
  text?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <Box size={36} />
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}
function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" />
      正在读取工作空间…
    </div>
  );
}
function Field({
  name,
  label: caption,
  type = "text",
  required = true,
  value,
  placeholder,
}: {
  name: string;
  label: string;
  type?: string;
  required?: boolean;
  value?: string;
  placeholder?: string;
}) {
  return (
    <label className="field">
      {caption}
      <input
        name={name}
        type={type}
        defaultValue={value}
        required={required}
        placeholder={placeholder}
        maxLength={type === "password" ? 128 : 1000}
      />
    </label>
  );
}

function Login({
  onLogin,
  demo,
}: {
  onLogin: (u: User) => void;
  demo: boolean;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [email, setEmail] = useState(""),
    [password, setPassword] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api<{ access_token: string; user: User }>(
        "/auth/login",
        post({ email, password }),
      );
      sessionStorage.setItem("lablink-token", result.access_token);
      onLogin(result.user);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-screen">
      <section className="login-story">
        <div className="brand">
          <span className="brand-icon">
            <FlaskConical size={23} />
          </span>
          LabLink<span className="brand-sub">LAB RESOURCES</span>
        </div>
        <div className="story-copy">
          <div className="eyebrow">LABLINK / 实验小站</div>
          <h1>
            共享设备，
            <br />
            一起做实验。
          </h1>
          <p>从预约一台设备开始，让实验室的资源、时间与想法，流动起来。</p>
          <div className="story-flow">
            <span>预约</span>
            <ArrowRight />
            <span>审批</span>
            <ArrowRight />
            <span>实验</span>
            <ArrowRight />
            <span>归还</span>
          </div>
        </div>
        <div className="story-footer">为实验室协作而设计 · LabLink</div>
      </section>
      <section className="login-form-wrap">
        <form onSubmit={submit} className="login-form">
          <div className="eyebrow">欢迎回来</div>
          <h2>登录你的实验空间</h2>
          <p>查看共享设备，安排下一次实验。</p>
          {error && (
            <div className="form-error" role="alert">
              {error}
            </div>
          )}
          <label className="field">
            工作邮箱
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@lablink.local"
            />
          </label>
          <label className="field">
            密码
            <input
              type="password"
              autoComplete="current-password"
              minLength={1}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <button className="primary login-submit" disabled={busy}>
            {busy ? <LoaderCircle className="spin" size={18} /> : null}
            进入工作空间
            <ArrowRight size={17} />
          </button>
          {demo && (
            <div className="demo-accounts">
              <strong>本机演示账号</strong>
              <p>全部为合成数据，可切换角色体验审批和权限隔离。</p>
              <div>
                {[
                  ["student", "成员"],
                  ["manager", "设备管理员"],
                  ["admin", "平台管理员"],
                  ["robot", "其他实验室"],
                ].map(([key, name]) => (
                  <button
                    type="button"
                    key={key}
                    onClick={() => {
                      setEmail(key + "@lablink.local");
                      setPassword("LabLink2026!");
                    }}
                  >
                    {name}
                  </button>
                ))}
              </div>
              <small>仅演示模式提供；请选择角色后点击登录。</small>
            </div>
          )}
        </form>
      </section>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(null),
    [authLoading, setAuthLoading] = useState(true),
    [demo, setDemo] = useState(false);
  const [page, setPage] = useState<PageName>(
      (location.hash.slice(1) || "overview") as PageName,
    ),
    [epoch, setEpoch] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [toast, setToast] = useState("");
  const [data, setData] = useState<any>(null),
    [modal, setModal] = useState<Modal | null>(null),
    [notices, setNotices] = useState<Notice[]>([]),
    [search, setSearch] = useState(""),
    [query, setQuery] = useState(""),
    [filter, setFilter] = useState(""),
    [offset, setOffset] = useState(0);
  const [schedule, setSchedule] = useState<
      { starts_at: string; ends_at: string; status: string }[]
    >([]),
    [scheduleError, setScheduleError] = useState(""),
    [deviceOptions, setDeviceOptions] = useState<Equipment[]>([]);
  const [markingRead, setMarkingRead] = useState(false);
  const [saving, setSaving] = useState(false),
    [formError, setFormError] = useState(""),
    [actionNote, setActionNote] = useState("");
  const modalRef = useRef<HTMLDialogElement>(null),
    priorFocus = useRef<HTMLElement | null>(null),
    idempotency = useRef({ key: crypto.randomUUID(), body: "" });
  const staff = user?.role === "admin" || user?.role === "manager";
  const flash = useCallback((text: string) => {
    setToast(text);
  }, []);
  const refresh = () => setEpoch((v) => v + 1);
  function navigate(target: PageName) {
    location.hash = target;
    setPage(target);
    setFilter("");
    setSearch("");
    setQuery("");
    setOffset(0);
    setData(null);
  }
  useEffect(() => {
    const t = setTimeout(() => {
      setQuery(search);
      setOffset(0);
    }, 250);
    return () => clearTimeout(t);
  }, [search]);
  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(""), 5000);
      return () => clearTimeout(t);
    }
  }, [toast]);
  useEffect(() => {
    const logout = () => {
      setUser(null);
      setAuthLoading(false);
    };
    window.addEventListener("lablink-logout", logout);
    fetch("/api/health")
      .then((r) => r.json())
      .then((r) => setDemo(r.demo))
      .catch(() => {});
    if (sessionStorage.getItem("lablink-token"))
      api<User>("/auth/me")
        .then(setUser)
        .catch(() => {})
        .finally(() => setAuthLoading(false));
    else setAuthLoading(false);
    return () => window.removeEventListener("lablink-logout", logout);
  }, []);
  useEffect(() => {
    const change = () => {
      const next = location.hash.slice(1) as PageName;
      setPage(titles[next] ? next : "overview");
      setOffset(0);
      setFilter("");
      setData(null);
    };
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    if (!user) return;
    let active = true;
    const load = () =>
      api<Notice[]>("/notifications")
        .then((r) => {
          if (active) setNotices(r);
        })
        .catch(() => {});
    load();
    const timer = setInterval(load, 15000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [user, epoch]);
  useEffect(() => {
    if (!user) return;
    const controller = new AbortController();
    setBusy(true);
    setError("");
    const params = new URLSearchParams({
      offset: String(offset),
      limit: "12",
      ...(query ? { q: query } : {}),
      ...(filter ? { status: filter } : {}),
    });
    const path =
      page === "overview"
        ? "/dashboard"
        : page === "notifications"
          ? "/notifications"
          : page === "operations"
            ? "/operations"
            : page === "approvals"
              ? "/bookings?" +
                new URLSearchParams({
                  status: "pending",
                  offset: String(offset),
                  limit: "12",
                })
              : "/" + page + "?" + params;
    api(path, { signal: controller.signal })
      .then(setData)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false);
      });
    return () => controller.abort();
  }, [user, page, epoch, offset, query, filter]);
  function openModal(value: Modal) {
    priorFocus.current = document.activeElement as HTMLElement;
    setModal(value);
    setFormError("");
    setActionNote("");
    setSchedule([]);
    setScheduleError("");
    idempotency.current = { key: crypto.randomUUID(), body: "" };
  }
  function closeModal() {
    if (saving) return;
    setModal(null);
    requestAnimationFrame(() => priorFocus.current?.focus());
  }
  useEffect(() => {
    if (modal && !modalRef.current?.open) modalRef.current?.showModal();
    else if (!modal) modalRef.current?.close();
    if (modal?.kind === "reserve") {
      const controller = new AbortController();
      api<typeof schedule>("/equipment/" + modal.item?.id + "/schedule", {
        signal: controller.signal,
      })
        .then(setSchedule)
        .catch((e) => {
          if (e.name !== "AbortError") setScheduleError(e.message);
        });
      return () => controller.abort();
    }
    if (modal?.kind === "fault" && !modal.item) {
      api<Page<Equipment>>("/equipment?limit=100")
        .then((r) => setDeviceOptions(r.items))
        .catch((e) => setFormError(e.message));
    }
  }, [modal]);
  async function submitModal(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!modal || !user) return;
    setSaving(true);
    setFormError("");
    const form = new FormData(e.currentTarget),
      value = (key: string) => String(form.get(key) || "");
    try {
      if (modal.kind === "reserve") {
        const body = JSON.stringify({
          equipment_id: modal.item!.id,
          starts_at: new Date(value("starts_at")).toISOString(),
          ends_at: new Date(value("ends_at")).toISOString(),
          purpose: value("purpose"),
        });
        if (idempotency.current.body && idempotency.current.body !== body)
          idempotency.current.key = crypto.randomUUID();
        idempotency.current.body = body;
        await api("/bookings", {
          method: "POST",
          body,
          headers: { "Idempotency-Key": idempotency.current.key },
        });
        flash("预约已提交，可在“我的预约”查看进展。");
      }
      if (modal.kind === "device") {
        await api(
          "/equipment",
          post({
            name: value("name"),
            code: value("code"),
            category: value("category"),
            location: value("location"),
            description: value("description"),
            approval_required: form.get("approval_required") === "on",
            team_id: user.role === "admin" ? value("team_id") : user.team_id,
          }),
        );
        flash("设备已加入资源目录。");
      }
      if (modal.kind === "fault") {
        await api(
          "/faults",
          post({
            equipment_id: modal.item?.id || value("equipment_id"),
            description: value("description"),
          }),
        );
        flash("报修已提交，设备暂停预约，受影响的预约将收到通知。");
      }
      if (modal.kind === "action") {
        await api(
          "/bookings/" + modal.item!.id + "/actions",
          post({ action: modal.action, note: actionNote }),
        );
        flash("预约状态已更新。");
      }
      if (modal.kind === "resolve") {
        await api(
          "/faults/" + modal.item!.id + "/resolve",
          post({ resolution: value("resolution") }),
        );
        flash("报修已关闭；没有其他未解决故障时，设备将恢复预约。");
      }
      if (modal.kind === "state") {
        await api("/equipment/" + modal.item!.id + "/status", {
          method: "PATCH",
          body: JSON.stringify({ status: value("status") }),
        });
        flash("设备状态已更新。");
      }
      if (modal.kind === "profile") {
        const updated = await api<User>("/auth/me", {
          method: "PATCH",
          body: JSON.stringify({
            full_name: value("full_name"),
            email: value("email"),
            bio: value("bio"),
            phone: value("phone"),
            student_id: value("student_id"),
            current_password: value("current_password"),
          }),
        });
        setUser(updated);
        flash("个人资料已保存。");
      }
      if (modal.kind === "user") {
        await api(
          "/users",
          post({
            email: value("email"),
            full_name: value("full_name"),
            password: value("password"),
            role: value("role"),
            team_id: value("team_id"),
          }),
        );
        flash("账号已创建，请通过可信渠道交付初始密码。");
      }
      setModal(null);
      refresh();
    } catch (e) {
      setFormError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  async function download() {
    try {
      const r = await fetch("/api/v1/bookings/export", {
        headers: {
          Authorization: "Bearer " + sessionStorage.getItem("lablink-token"),
        },
      });
      if (!r.ok) throw new Error("导出失败");
      const url = URL.createObjectURL(await r.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = "bookings.csv";
      a.click();
      URL.revokeObjectURL(url);
      flash("已导出有权查看的预约记录。");
    } catch (e) {
      flash((e as Error).message);
    }
  }
  useEffect(() => {
    document.querySelector(".main-shell main")?.scrollTo({ top: 0 });
  }, [page]);
  if (authLoading) return <Loading />;
  if (!user)
    return (
      <Login
        demo={demo}
        onLogin={(u) => {
          setUser(u);
          navigate("overview");
        }}
      />
    );
  const count = data?.total || 0;
  function pagination() {
    return count > 12 ? (
      <div className="pagination">
        <span>
          共 {count} 条 · 第 {Math.floor(offset / 12) + 1} 页
        </span>
        <button
          disabled={!offset}
          onClick={() => setOffset((v) => Math.max(0, v - 12))}
        >
          <ChevronLeft size={16} />
          上一页
        </button>
        <button
          disabled={offset + 12 >= count}
          onClick={() => setOffset((v) => v + 12)}
        >
          下一页
          <ChevronRight size={16} />
        </button>
      </div>
    ) : null;
  }
  function bookingTable(rows: Booking[]) {
    return !rows.length ? (
      <Empty
        title={page === "approvals" ? "没有待处理的申请" : "预约记录从这里开始"}
        text="选择一台设备，安排一个适合实验的时段。"
        action={
          <button className="primary" onClick={() => navigate("equipment")}>
            去设备资源
            <ArrowRight size={16} />
          </button>
        }
      />
    ) : (
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>设备 / 用途</th>
              {staff && <th>申请人</th>}
              <th>预约时段</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((b) => (
              <tr key={b.id}>
                <td>
                  <strong>{b.equipment_name || "设备预约"}</strong>
                  <p className="cell-note">{b.purpose}</p>
                  {b.decision_note && (
                    <small className="decision-note">
                      备注：{b.decision_note}
                    </small>
                  )}
                </td>
                {staff && <td>{b.user_name || "—"}</td>}
                <td className="time-cell">
                  {date(b.starts_at)}
                  <br />
                  <span>至 {date(b.ends_at)}</span>
                </td>
                <td>
                  <Badge status={b.status} />
                </td>
                <td>
                  <div className="row-actions">
                    {staff &&
                      b.status === "pending" &&
                      b.user_id !== user!.id && (
                        <>
                          <button
                            className="text-button"
                            onClick={() =>
                              openModal({
                                kind: "action",
                                item: b,
                                action: "approve",
                              })
                            }
                          >
                            通过
                          </button>
                          <button
                            className="text-button danger"
                            onClick={() =>
                              openModal({
                                kind: "action",
                                item: b,
                                action: "reject",
                              })
                            }
                          >
                            拒绝
                          </button>
                        </>
                      )}
                    {b.status === "approved" && b.user_id === user!.id && (
                      <button
                        className="text-button"
                        onClick={() =>
                          openModal({
                            kind: "action",
                            item: b,
                            action: "checkout",
                          })
                        }
                      >
                        领用
                      </button>
                    )}
                    {b.status === "checked_out" &&
                      (staff || b.user_id === user!.id) && (
                        <button
                          className="text-button"
                          onClick={() =>
                            openModal({
                              kind: "action",
                              item: b,
                              action: "return",
                            })
                          }
                        >
                          归还
                        </button>
                      )}
                    {["pending", "approved"].includes(b.status) &&
                      (staff || b.user_id === user!.id) && (
                        <button
                          className="text-button subtle"
                          onClick={() =>
                            openModal({
                              kind: "action",
                              item: b,
                              action: "cancel",
                            })
                          }
                        >
                          取消预约
                        </button>
                      )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  const title = titles[page] || titles.overview;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#overview">
          <span className="brand-icon">
            <FlaskConical size={22} />
          </span>
          LabLink
        </a>
        <div className="workspace-label">
          <span className="workspace-dot" />
          <div>
            {label[user.team_id] || user.team_id}
            <small>LAB WORKSPACE</small>
          </div>
        </div>
        <div className="nav-label">工作空间</div>
        <nav>
          {navigation
            .filter(
              (n) =>
                (!("staff" in n) || staff) &&
                (!("admin" in n) || user.role === "admin"),
            )
            .map((n) => (
              <button
                key={n.id}
                aria-label={n.name}
                className={page === n.id ? "nav-item selected" : "nav-item"}
                onClick={() => navigate(n.id)}
              >
                <n.icon size={18} />
                <span>{n.name}</span>
                {n.id === "notifications" &&
                  notices.filter((x) => !x.read_at).length > 0 && (
                    <b>{notices.filter((x) => !x.read_at).length}</b>
                  )}
              </button>
            ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <span className="note-circle">
              <FlaskConical size={20} />
            </span>
            <strong>实验有安排，灵感不掉线</strong>
            <p>预约、使用、归还，都在这里。</p>
          </div>
          <button
            className="logout"
            onClick={() => {
              sessionStorage.removeItem("lablink-token");
              setUser(null);
            }}
          >
            <LogOut size={16} />
            退出登录
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            工作空间<span>/</span>
            <strong>{title[0]}</strong>
          </div>
          <div className="topbar-right">
            {demo && <span className="demo-tag">演示空间</span>}
            <button
              className="icon-button notification-button"
              aria-label="打开消息中心"
              onClick={() => navigate("notifications")}
            >
              <Bell size={19} />
              {notices.some((n) => !n.read_at) && <i />}
            </button>
            <span className="topbar-divider" />
            <button
              type="button"
              className="user-chip"
              aria-label="个人资料"
              onClick={() => openModal({ kind: "profile" })}
            >
              <span className="avatar">{user.full_name?.slice(0, 1)}</span>
              <div>
                <strong>{user.full_name}</strong>
                <small>{label[user.role]}</small>
              </div>
            </button>
          </div>
        </header>
        <main>
          <div className="page-header">
            <div>
              <div className="eyebrow">
                {page === "overview" ? "我的实验空间" : "实验小站"}
              </div>
              <h1>{title[0]}</h1>
              <p>{title[1]}</p>
            </div>
            <div className="page-actions">
              {page === "notifications" && (
                <button
                  className="primary"
                  disabled={markingRead || !notices.some((n) => !n.read_at)}
                  onClick={async () => {
                    setMarkingRead(true);
                    try {
                      const result = await api<{ updated: number }>(
                        "/notifications/read-all",
                        post({}),
                      );
                      refresh();
                      flash(
                        result.updated
                          ? `已将 ${result.updated} 条消息标为已读。`
                          : "所有消息都已读。",
                      );
                    } catch (e) {
                      flash((e as Error).message);
                    } finally {
                      setMarkingRead(false);
                    }
                  }}
                >
                  {markingRead ? (
                    <LoaderCircle className="spin" size={16} />
                  ) : (
                    <CheckCircle2 size={16} />
                  )}
                  全部标为已读
                </button>
              )}

              <button
                className="icon-button"
                aria-label="刷新当前页面"
                onClick={refresh}
              >
                <RefreshCw size={18} />
              </button>
              {page === "equipment" && staff && (
                <button
                  className="primary"
                  onClick={() => openModal({ kind: "device" })}
                >
                  <Plus size={17} />
                  添加设备
                </button>
              )}
              {page === "faults" && (
                <button
                  className="primary"
                  onClick={() => openModal({ kind: "fault" })}
                >
                  <Plus size={17} />
                  发起报修
                </button>
              )}
              {page === "users" && user.role === "admin" && (
                <button
                  className="primary"
                  onClick={() => openModal({ kind: "user" })}
                >
                  <Plus size={17} />
                  添加成员
                </button>
              )}
            </div>
          </div>
          {page === "equipment" && (
            <div className="toolbar">
              <div className="search-field">
                <Search size={18} />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="搜索设备名称或编号"
                  aria-label="搜索设备"
                />
              </div>
              <select
                aria-label="筛选设备状态"
                value={filter}
                onChange={(e) => {
                  setFilter(e.target.value);
                  setOffset(0);
                }}
              >
                <option value="">全部状态</option>
                <option value="available">可预约</option>
                <option value="maintenance">维护中</option>
                <option value="retired">已停用</option>
              </select>
              <span className="results-count">{count} 台设备</span>
            </div>
          )}
          {page === "bookings" && (
            <div className="toolbar">
              <div className="filter-tabs">
                {[
                  ["", "全部"],
                  ["pending", "待审批"],
                  ["approved", "已通过"],
                  ["checked_out", "使用中"],
                  ["returned", "已归还"],
                ].map(([key, name]) => (
                  <button
                    className={filter === key ? "active" : ""}
                    key={key}
                    onClick={() => {
                      setFilter(key);
                      setOffset(0);
                    }}
                  >
                    {name}
                  </button>
                ))}
              </div>
              {staff && (
                <button onClick={download}>
                  <Download size={16} />
                  导出 CSV
                </button>
              )}
            </div>
          )}
          {busy ? (
            <Loading />
          ) : error ? (
            <div className="error-panel" role="alert">
              <h3>暂时无法读取数据</h3>
              <p>{error}</p>
              <button onClick={refresh}>
                <RefreshCw size={16} />
                重新加载
              </button>
            </div>
          ) : (
            data && (
              <>
                {page === "overview" && (
                  <Overview
                    data={data as Dashboard}
                    name={user.full_name}
                    onNavigate={navigate}
                  />
                )}
                {page === "equipment" && (
                  <>
                    {data.items.length ? (
                      <div className="equipment-grid">
                        {(data.items as Equipment[]).map((item, index) => (
                          <article className="equipment-card" key={item.id}>
                            <div className={"equipment-art art-" + (index % 4)}>
                              <span className="equipment-code">
                                {item.code}
                              </span>
                              <Monitor size={66} strokeWidth={1.1} />
                              <span className="art-caption">
                                {item.category}
                              </span>
                              <Badge status={item.status} />
                            </div>
                            <div className="equipment-body">
                              <h3>{item.name}</h3>
                              <div className="location">
                                <MapPin size={14} />
                                {item.location}
                              </div>
                              <p>
                                {item.description ||
                                  "暂无设备说明，请联系管理员了解使用要求。"}
                              </p>
                              <div className="device-policy">
                                <ShieldCheck size={14} />
                                {item.approval_required
                                  ? "管理员审批后使用"
                                  : "无需审批，预约后可领用"}
                              </div>
                              <div className="device-actions">
                                <button
                                  className="primary"
                                  disabled={item.status !== "available"}
                                  onClick={() =>
                                    openModal({ kind: "reserve", item })
                                  }
                                >
                                  预约设备
                                  <ArrowUpRight size={16} />
                                </button>
                                <button
                                  className="icon-button"
                                  aria-label={"报修 " + item.name}
                                  disabled={item.status === "retired"}
                                  onClick={() =>
                                    openModal({ kind: "fault", item })
                                  }
                                >
                                  <Wrench size={17} />
                                </button>
                                {staff && (
                                  <button
                                    className="icon-button"
                                    aria-label={"管理 " + item.name}
                                    onClick={() =>
                                      openModal({ kind: "state", item })
                                    }
                                  >
                                    <Activity size={17} />
                                  </button>
                                )}
                              </div>
                            </div>
                          </article>
                        ))}
                      </div>
                    ) : (
                      <Empty
                        title="没有匹配的设备"
                        text="试试其他关键词，或请管理员添加设备。"
                      />
                    )}
                    {pagination()}
                  </>
                )}
                {(page === "bookings" || page === "approvals") && (
                  <section className="panel table-panel">
                    {bookingTable(data.items)}
                    {pagination()}
                  </section>
                )}
                {page === "faults" && (
                  <section className="panel">
                    {!data.items.length ? (
                      <Empty
                        title="暂无报修记录"
                        text="发现问题及时报修，受影响的预约会自动取消并通知申请人。"
                      />
                    ) : (
                      <div className="fault-list">
                        {(data.items as Fault[]).map((f) => (
                          <article className="fault-item" key={f.id}>
                            <span className="fault-icon">
                              <Wrench size={20} />
                            </span>
                            <div className="fault-copy">
                              <h3>{f.equipment_name}</h3>
                              <p>{f.description}</p>
                              <small>{date(f.created_at)}</small>
                              {f.resolution && (
                                <div className="resolution">
                                  <CheckCircle2 size={15} />
                                  {f.resolution}
                                </div>
                              )}
                            </div>
                            <div className="fault-action">
                              <Badge status={f.status} />
                              {staff && f.status === "open" && (
                                <button
                                  onClick={() =>
                                    openModal({ kind: "resolve", item: f })
                                  }
                                >
                                  处理报修
                                  <ArrowRight size={15} />
                                </button>
                              )}
                            </div>
                          </article>
                        ))}
                      </div>
                    )}
                    {pagination()}
                  </section>
                )}
                {page === "notifications" && (
                  <section className="panel">
                    {!data.length ? (
                      <Empty
                        title="消息箱很安静"
                        text="预约状态变化和使用提醒将出现在这里。"
                      />
                    ) : (
                      (data as Notice[]).map((n) => (
                        <button
                          key={n.id}
                          aria-label={n.title}
                          className={
                            "notice-row " + (!n.read_at ? "unread" : "")
                          }
                          onClick={async () => {
                            try {
                              await api(
                                "/notifications/" + n.id + "/read",
                                post({}),
                              );
                              refresh();
                            } catch (e) {
                              flash((e as Error).message);
                            }
                          }}
                        >
                          <span className="notice-icon">
                            <Bell size={18} />
                          </span>
                          <span>
                            <strong>
                              {n.title}
                              {!n.read_at && <i />}
                            </strong>
                            <p>{n.body}</p>
                            <small>{date(n.created_at)}</small>
                          </span>
                          {!n.read_at && <Check size={17} />}
                        </button>
                      ))
                    )}
                  </section>
                )}
                {page === "audit" && (
                  <section className="panel table-panel">
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>时间</th>
                            <th>操作</th>
                            <th>资源编号</th>
                            <th>实验室</th>
                            <th>备注</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(data.items as Audit[]).map((a) => (
                            <tr key={a.id}>
                              <td>{date(a.created_at)}</td>
                              <td>
                                <code>{a.action}</code>
                              </td>
                              <td>
                                <code>{a.target_id.slice(0, 12)}</code>
                              </td>
                              <td>{label[a.team_id] || a.team_id}</td>
                              <td>{a.detail || "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {!data.items.length && <Empty title="暂无操作记录" />}
                    {pagination()}
                  </section>
                )}
                {page === "users" && (
                  <section className="panel table-panel">
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>成员</th>
                            <th>工作邮箱</th>
                            <th>实验室</th>
                            <th>角色</th>
                            <th>状态</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(data as User[]).map((u) => (
                            <tr key={u.id}>
                              <td>
                                <span className="inline-user">
                                  <span className="avatar small">
                                    {u.full_name.slice(0, 1)}
                                  </span>
                                  {u.full_name}
                                </span>
                              </td>
                              <td>{u.email}</td>
                              <td>{label[u.team_id] || u.team_id}</td>
                              <td>{label[u.role]}</td>
                              <td>
                                <span className="badge available">正常</span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                )}
                {page === "operations" && (
                  <>
                    <div className="stat-grid">
                      {["pending", "delivered", "dead", "skipped"].map((k) => (
                        <Stat
                          key={k}
                          name={k === "pending" ? "等待投递" : label[k]}
                          value={data.counts[k] || 0}
                          icon={<Bell size={20} />}
                          note="站内通知事件"
                        />
                      ))}
                    </div>
                    <section className="panel">
                      <h2>失败通知</h2>
                      <p className="section-description">
                        业务和通知事件同事务保存。投递最多尝试 5
                        次，失败后可在此重试。
                      </p>
                      {!data.dead_letters.length ? (
                        <Empty
                          title="没有待重试的通知"
                          text="通知投递正常，系统每 5 秒检查一次待处理事件。"
                        />
                      ) : (
                        data.dead_letters.map(
                          (event: {
                            id: string;
                            title: string;
                            attempts: number;
                          }) => (
                            <div className="retry-row" key={event.id}>
                              <span>
                                {event.title} · 已尝试 {event.attempts} 次
                              </span>
                              <button
                                onClick={async () => {
                                  try {
                                    await api(
                                      "/operations/" + event.id + "/retry",
                                      post({}),
                                    );
                                    refresh();
                                    flash("已重新加入投递队列。");
                                  } catch (e) {
                                    flash((e as Error).message);
                                  }
                                }}
                              >
                                重新投递
                              </button>
                            </div>
                          ),
                        )
                      )}
                    </section>
                  </>
                )}
              </>
            )
          )}
          <footer>
            LabLink <span>·</span> 实验室资源协作平台 <span>·</span>{" "}
            {demo ? "合成数据演示空间" : "共享有序，探索自由"}
          </footer>
        </main>
      </div>
      {toast && (
        <div className="toast" role="status">
          <CheckCircle2 size={18} />
          <span>{toast}</span>
          <button
            className="icon-button"
            aria-label="关闭提示"
            onClick={() => setToast("")}
          >
            <X size={16} />
          </button>
        </div>
      )}
      <dialog
        ref={modalRef}
        className="modal"
        onCancel={(e) => {
          e.preventDefault();
          closeModal();
        }}
        aria-labelledby="modal-title"
        onClick={(e) => {
          if (e.target === e.currentTarget) closeModal();
        }}
      >
        {modal && (
          <form onSubmit={submitModal}>
            <div className="modal-heading">
              <div>
                <span className="eyebrow">实验小站</span>
                <h2 id="modal-title">
                  {
                    {
                      reserve: "预约设备",
                      fault: "提交设备报修",
                      device: "添加共享设备",
                      action:
                        {
                          approve: "通过预约",
                          reject: "拒绝预约",
                          cancel: "取消预约",
                          checkout: "确认领用",
                          return: "确认归还",
                        }[modal.action || ""] || "处理预约",
                      resolve: "记录维修结果",
                      state: "管理设备状态",
                      user: "添加实验室成员",
                      profile: "个人资料",
                    }[modal.kind]
                  }
                </h2>
              </div>
              <button
                type="button"
                className="icon-button"
                aria-label="关闭弹窗"
                disabled={saving}
                onClick={closeModal}
              >
                <X size={21} />
              </button>
            </div>
            {formError && (
              <div className="form-error" role="alert">
                {formError}
              </div>
            )}
            {modal.kind === "reserve" && (
              <>
                <div className="modal-resource">
                  <Monitor size={26} />
                  <div>
                    <strong>{(modal.item as Equipment).name}</strong>
                    <small>{(modal.item as Equipment).location}</small>
                  </div>
                  <Badge status={(modal.item as Equipment).status} />
                </div>
                <div className="form-two">
                  <Field
                    name="starts_at"
                    label="开始时间"
                    type="datetime-local"
                    value={localTime(1)}
                  />
                  <Field
                    name="ends_at"
                    label="结束时间"
                    type="datetime-local"
                    value={localTime(3)}
                  />
                </div>
                <label className="field">
                  实验用途
                  <textarea
                    name="purpose"
                    required
                    minLength={3}
                    maxLength={1000}
                    placeholder="简要说明实验内容，方便管理员安排资源。"
                  />
                </label>
                <div className="schedule-box">
                  <h4>
                    <Clock size={15} />
                    已占用时段
                  </h4>
                  {scheduleError ? (
                    <p className="danger">{scheduleError}</p>
                  ) : !schedule.length ? (
                    <p>暂无未来占用记录。最终是否可预约以提交时的检查为准。</p>
                  ) : (
                    schedule.map((s, i) => (
                      <div key={i}>
                        <span>
                          {date(s.starts_at)} — {date(s.ends_at)}
                        </span>
                        <Badge status={s.status} />
                      </div>
                    ))
                  )}
                </div>
                <p className="form-help">
                  时间按你电脑所在时区填写。单次最多 24 小时，可提前 30
                  天预约；待审批也会占用时段。
                </p>
              </>
            )}
            {modal.kind === "device" && (
              <>
                <div className="form-two">
                  <Field name="name" label="设备名称" />
                  <Field
                    name="code"
                    label="唯一设备编号"
                    placeholder="如 VIS-005"
                  />
                </div>
                <div className="form-two">
                  <Field name="category" label="设备类别" value="计算设备" />
                  <Field
                    name="location"
                    label="存放位置"
                    placeholder="楼栋 / 房间"
                  />
                </div>
                {user.role === "admin" && (
                  <Field
                    name="team_id"
                    label="所属实验室标识"
                    value={user.team_id}
                  />
                )}
                <label className="field">
                  使用说明
                  <textarea
                    name="description"
                    maxLength={2000}
                    placeholder="规格、适用实验、注意事项"
                  />
                </label>
                <label className="checkbox-field">
                  <input
                    name="approval_required"
                    type="checkbox"
                    defaultChecked
                  />
                  预约需要管理员审批
                </label>
              </>
            )}
            {modal.kind === "fault" && (
              <>
                {modal.item ? (
                  <div className="modal-resource">
                    <Wrench size={24} />
                    <strong>{(modal.item as Equipment).name}</strong>
                  </div>
                ) : (
                  <label className="field">
                    选择设备
                    <select name="equipment_id" required>
                      <option value="">请选择</option>
                      {deviceOptions
                        .filter((d) => d.status !== "retired")
                        .map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.name} · {d.code}
                          </option>
                        ))}
                    </select>
                  </label>
                )}
                <label className="field">
                  遇到了什么问题？
                  <textarea
                    name="description"
                    minLength={5}
                    maxLength={2000}
                    required
                    placeholder="描述故障现象、发生时间和已尝试的处理方式。"
                  />
                </label>
                <div className="callout">
                  报修后设备会暂停预约，尚未领用的预约将取消并通知申请人。请确认不是普通的使用咨询。
                </div>
              </>
            )}
            {modal.kind === "action" && (
              <>
                <div className="modal-resource">
                  <CalendarDays size={24} />
                  <div>
                    <strong>{(modal.item as Booking).equipment_name}</strong>
                    <small>
                      {date((modal.item as Booking).starts_at)} —{" "}
                      {date((modal.item as Booking).ends_at)}
                    </small>
                  </div>
                </div>
                <p className="action-description">
                  {
                    {
                      approve:
                        "审批通过后，申请人可在开始前 15 分钟至结束前领用设备。",
                      reject: "拒绝后会释放时段并通知申请人，请说明原因。",
                      cancel: "取消后释放这个预约时段，原记录仍会保留。",
                      checkout: "请确认设备和配件完好，领用后请按时归还。",
                      return:
                        "请确认设备已放回原位，配件完整。如有故障，请另行报修。",
                    }[modal.action || "approve"]
                  }
                </p>
                <label className="field">
                  {modal.action === "reject" ? "拒绝原因" : "补充说明（选填）"}
                  <textarea
                    value={actionNote}
                    onChange={(e) => setActionNote(e.target.value)}
                    maxLength={1000}
                    required={modal.action === "reject"}
                  />
                </label>
              </>
            )}
            {modal.kind === "resolve" && (
              <>
                <div className="callout">
                  {(modal.item as Fault).description}
                </div>
                <label className="field">
                  处理结果
                  <textarea
                    name="resolution"
                    required
                    minLength={3}
                    maxLength={2000}
                    placeholder="说明故障原因、处理措施以及是否已验证恢复。"
                  />
                </label>
                <p className="form-help">
                  只有此设备的全部报修关闭后，才会自动恢复可预约状态。
                </p>
              </>
            )}
            {modal.kind === "state" && (
              <>
                <div className="modal-resource">
                  <Monitor size={24} />
                  <strong>{(modal.item as Equipment).name}</strong>
                </div>
                <label className="field">
                  设备状态
                  <select
                    name="status"
                    defaultValue={(modal.item as Equipment).status}
                  >
                    <option value="available">可预约</option>
                    <option value="maintenance">维护中</option>
                    <option value="retired">停用（不可恢复）</option>
                  </select>
                </label>
                <div className="callout">
                  维护或停用会取消尚未领用的预约并发送通知。有未解决故障时，请先处理报修。
                </div>
              </>
            )}
            {modal.kind === "profile" && (
              <>
                <div className="profile-summary">
                  <span className="avatar">{user.full_name?.slice(0, 1)}</span>
                  <div>
                    <strong>{user.full_name}</strong>
                    <small>
                      {label[user.role]} · {label[user.team_id] || user.team_id}
                    </small>
                  </div>
                </div>
                <Field
                  name="full_name"
                  label="姓名 / 昵称"
                  value={user.full_name}
                />
                <Field
                  name="email"
                  label="登录邮箱"
                  type="email"
                  value={user.email}
                />
                <Field
                  name="current_password"
                  label="当前密码（仅更改邮箱时填写）"
                  type="password"
                  required={false}
                />
                <label className="field">学号（选填）<input name="student_id" type="text" maxLength={32} pattern="[A-Za-z0-9_-]*" defaultValue={user.student_id || ""} placeholder="填写学号，支持字母和数字"/></label>
                <label className="field">
                  联系电话（选填）
                  <input
                    name="phone"
                    type="tel"
                    maxLength={30}
                    defaultValue={user.phone || ""}
                  />
                </label>
                <label className="field">
                  个人简介（选填）
                  <textarea
                    name="bio"
                    maxLength={500}
                    defaultValue={user.bio || ""}
                    placeholder="研究方向、常用设备，或其他想补充的信息。"
                  />
                </label>
                <p className="form-help">
                  角色与所属实验室由管理员分配。更改邮箱后，下次请使用新邮箱登录。
                </p>
              </>
            )}
            {modal.kind === "user" && (
              <>
                <div className="form-two">
                  <Field name="full_name" label="成员姓名" />
                  <Field name="email" label="工作邮箱" type="email" />
                </div>
                <Field
                  name="password"
                  label="初始密码（至少 10 位）"
                  type="password"
                />
                <div className="form-two">
                  <Field name="team_id" label="实验室标识" value="vision" />
                  <label className="field">
                    角色
                    <select name="role">
                      <option value="member">实验室成员</option>
                      <option value="manager">设备管理员</option>
                    </select>
                  </label>
                </div>
                <p className="form-help">
                  实验室标识必须与设备所属实验室一致。创建后请通过可信渠道交付账号。
                </p>
              </>
            )}
            <div className="modal-footer">
              <button type="button" disabled={saving} onClick={closeModal}>
                取消
              </button>
              <button
                className={
                  "primary " +
                  (["cancel", "reject"].includes(modal.action || "")
                    ? "red"
                    : "")
                }
                disabled={saving}
              >
                {saving ? (
                  <LoaderCircle className="spin" size={17} />
                ) : (
                  <Check size={17} />
                )}{" "}
                {saving
                  ? "正在保存…"
                  : modal.kind === "reserve"
                    ? "提交预约"
                    : "确认"}
              </button>
            </div>
          </form>
        )}
      </dialog>
    </div>
  );
}

function Stat({
  name,
  value,
  icon,
  note,
}: {
  name: string;
  value: number;
  icon: ReactNode;
  note: string;
}) {
  return (
    <div className="stat">
      <div>
        <span>{name}</span>
        <span className="stat-icon">{icon}</span>
      </div>
      <strong>{value.toString().padStart(2, "0")}</strong>
      <small>{note}</small>
    </div>
  );
}
function Overview({
  data,
  name,
  onNavigate,
}: {
  data: Dashboard;
  name: string;
  onNavigate: (p: PageName) => void;
}) {
  return (
    <>
      <section className="welcome">
        <div>
          <span className="welcome-label">今天的实验计划</span>
          <h2>{name}，欢迎回到实验室。</h2>
          <p>选好设备和时间，开始今天的实验。</p>
          <button onClick={() => onNavigate("equipment")}>
            探索设备资源
            <ArrowUpRight size={17} />
          </button>
        </div>
        <div className="welcome-art" aria-hidden="true">
          <div className="art-ring" />
          <div className="art-monitor">
            <Monitor size={90} strokeWidth={1} />
            <span>LAB TIME ✦</span>
          </div>
          <div className="art-small">
            <FlaskConical size={27} />
          </div>
        </div>
      </section>
      <div className="stat-grid">
        <Stat
          name="共享设备"
          value={data.equipment_total}
          icon={<Monitor size={20} />}
          note={`${data.available} 台设备允许预约`}
        />
        <Stat
          name="待审批预约"
          value={data.pending}
          icon={<ClipboardCheck size={20} />}
          note="等待管理员确认"
        />
        <Stat
          name="已通过 / 使用中"
          value={data.active}
          icon={<CalendarDays size={20} />}
          note={
            data.overdue
              ? `${data.overdue} 条预约逾期未归还`
              : "按时领用，及时归还"
          }
        />
        <Stat
          name="已完成实验"
          value={data.completed}
          icon={<CheckCircle2 size={20} />}
          note="按已归还的预约数量统计"
        />
      </div>
      <div className="overview-columns">
        <section className="panel">
          <div className="section-heading">
            <h2>最近的预约</h2>
            <button
              className="text-button"
              onClick={() => onNavigate("bookings")}
            >
              查看全部
              <ArrowRight size={15} />
            </button>
          </div>
          {!data.recent_bookings.length ? (
            <Empty
              title="还没有预约"
              text="你的实验计划，从选择一台设备开始。"
            />
          ) : (
            data.recent_bookings.map((b) => (
              <div className="recent-booking" key={b.id}>
                <div className="date-tile">
                  <CalendarDays size={21} />
                </div>
                <div>
                  <strong>{b.purpose}</strong>
                  <small>
                    {date(b.starts_at)} — {date(b.ends_at)}
                  </small>
                </div>
                <Badge status={b.status} />
              </div>
            ))
          )}
        </section>
        <section className="panel guide-panel">
          <span className="guide-icon">
            <FlaskConical size={25} />
          </span>
          <h2>一次有序的共享</h2>
          <p>不只是借用设备，也是让每个人的实验顺利发生。</p>
          <ol>
            <li>
              <b>01</b>
              <div>
                <strong>选择设备与时段</strong>
                <small>先看占用情况，再提交实验用途。</small>
              </div>
            </li>
            <li>
              <b>02</b>
              <div>
                <strong>确认审批与领用</strong>
                <small>按预约时间到场，检查设备配件。</small>
              </div>
            </li>
            <li>
              <b>03</b>
              <div>
                <strong>及时归还与反馈</strong>
                <small>归还确认，有故障及时发起报修。</small>
              </div>
            </li>
          </ol>
          <div className="guide-foot">
            当前维护中：{data.maintenance} 台设备
            <Wrench size={16} />
          </div>
        </section>
      </div>
    </>
  );
}
