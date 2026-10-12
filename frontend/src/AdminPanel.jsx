import { useCallback, useEffect, useState } from "react";
import { authenticatedRequest } from "./api";

const PAGE_SIZE = 25;

function formatCreatedAt(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Unknown"
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
      }).format(date);
}

export default function AdminPanel({
  accessToken,
  currentUserId,
  onSessionExpired,
  onWorkspace,
}) {
  const [users, setUsers] = useState([]);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [updatingId, setUpdatingId] = useState("");

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        offset: String(offset),
        limit: String(PAGE_SIZE),
      });
      if (search) params.set("search", search);
      const result = await authenticatedRequest(
        `/api/v1/admin/users?${params}`,
        {},
        accessToken,
        onSessionExpired
      );
      setUsers(result.users);
      setTotal(result.total);
    } catch (requestError) {
      setError(requestError.message || "Could not load registered users.");
    } finally {
      setLoading(false);
    }
  }, [accessToken, offset, onSessionExpired, search]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (!cancelled) void loadUsers();
    });
    return () => {
      cancelled = true;
    };
  }, [loadUsers]);

  async function updateAccess(user) {
    const action = user.is_active ? "revoke" : "grant";
    const confirmation = user.is_active
      ? `Revoke application access for ${user.email}? Their saved interviews and reports will be kept.`
      : `Grant application access to ${user.email}?`;
    if (!window.confirm(confirmation)) return;

    setUpdatingId(user.id);
    setError("");
    setNotice("");
    try {
      const updated = await authenticatedRequest(
        `/api/v1/admin/users/${encodeURIComponent(user.id)}/access`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_active: !user.is_active }),
        },
        accessToken,
        onSessionExpired
      );
      setUsers((current) =>
        current.map((item) => (item.id === updated.id ? updated : item))
      );
      setNotice(
        `Application access ${action === "grant" ? "granted to" : "revoked for"} ${updated.email}.`
      );
    } catch (requestError) {
      setError(requestError.message || "Could not update application access.");
    } finally {
      setUpdatingId("");
    }
  }

  function submitSearch(event) {
    event.preventDefault();
    const nextSearch = searchInput.trim();
    if (nextSearch.length > 254) {
      setError("Search must be 254 characters or fewer.");
      return;
    }
    setError("");
    setOffset(0);
    setSearch(nextSearch);
  }

  return (
    <main className="admin-page">
      <header className="admin-page-header">
        <div>
          <p className="eyebrow">ADMINISTRATION</p>
          <h1>User access</h1>
          <p>Manage who can use the AgentHire interview workspace.</p>
        </div>
        <button
          className="button button-quiet"
          type="button"
          onClick={onWorkspace}
        >
          Back to workspace
        </button>
      </header>

      <section className="admin-card" aria-labelledby="registered-users-title">
        <div className="admin-card-heading">
          <div>
            <h2 id="registered-users-title">Registered users</h2>
            <p>{total} account{total === 1 ? "" : "s"}</p>
          </div>
          <button
            className="button button-quiet"
            type="button"
            onClick={() => void loadUsers()}
            disabled={loading}
          >
            Refresh
          </button>
        </div>

        <form className="admin-search" onSubmit={submitSearch}>
          <label className="sr-only" htmlFor="admin-user-search">
            Search users by email
          </label>
          <input
            id="admin-user-search"
            type="search"
            maxLength={254}
            placeholder="Search by email"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
          />
          <button className="button button-primary" type="submit">
            Search
          </button>
        </form>

        {notice && <p className="admin-notice" role="status">{notice}</p>}
        {error && <p className="admin-error" role="alert">{error}</p>}

        {loading ? (
          <p className="admin-loading" role="status">Loading users…</p>
        ) : users.length === 0 ? (
          <p className="admin-empty">
            {search ? "No users match that email search." : "No registered users found."}
          </p>
        ) : (
          <div className="admin-table-scroll">
            <table className="admin-user-table">
              <thead>
                <tr>
                  <th scope="col">Email</th>
                  <th scope="col">Created</th>
                  <th scope="col">Role</th>
                  <th scope="col">Application access</th>
                  <th scope="col"><span className="sr-only">Action</span></th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td data-label="Email">{user.email}</td>
                    <td data-label="Created">{formatCreatedAt(user.created_at)}</td>
                    <td data-label="Role">
                      <span className={`admin-badge role-${user.role}`}>
                        {user.role}
                      </span>
                    </td>
                    <td data-label="Application access">
                      <span className={`admin-badge ${user.is_active ? "access-enabled" : "access-disabled"}`}>
                        {user.is_active ? "Enabled" : "Not granted"}
                      </span>
                    </td>
                    <td className="admin-action-cell">
                      <button
                        className={`button ${user.is_active ? "button-quiet" : "button-primary"} admin-access-button`}
                        type="button"
                        disabled={updatingId === user.id || user.id === currentUserId}
                        title={user.id === currentUserId ? "You cannot change your own access." : undefined}
                        onClick={() => void updateAccess(user)}
                      >
                        {updatingId === user.id
                          ? "Saving…"
                          : user.is_active
                            ? "Revoke"
                            : "Grant access"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="admin-pagination">
          <span>
            {total === 0
              ? "0 users"
              : `${offset + 1}–${Math.min(offset + users.length, total)} of ${total}`}
          </span>
          <div>
            <button
              className="button button-quiet"
              type="button"
              disabled={offset === 0 || loading}
              onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
            >
              Previous
            </button>
            <button
              className="button button-quiet"
              type="button"
              disabled={offset + PAGE_SIZE >= total || loading}
              onClick={() => setOffset((value) => value + PAGE_SIZE)}
            >
              Next
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
