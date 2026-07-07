import React, { useState, useEffect } from 'react'
import { useTranslation } from '../i18n'
import { fetchUsers, updateUserStatus, updateUserRole, deleteUser } from '../api'

export default function UserManagementPage() {
  const { t } = useTranslation()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionLoading, setActionLoading] = useState(null)

  useEffect(() => {
    loadUsers()
  }, [])

  async function loadUsers() {
    try {
      setLoading(true)
      const data = await fetchUsers()
      setUsers(data)
      setError(null)
    } catch (err) {
      setError(err.message || 'Impossible de charger les utilisateurs')
    } finally {
      setLoading(false)
    }
  }

  async function handleStatusChange(userId, newStatus) {
    try {
      setActionLoading(userId)
      await updateUserStatus(userId, newStatus)
      setUsers(prev =>
        prev.map(u => (u.id === userId ? { ...u, status: newStatus } : u))
      )
    } catch (err) {
      alert(err.message)
    } finally {
      setActionLoading(null)
    }
  }

  async function handleRoleChange(userId, newRole) {
    try {
      setActionLoading(userId)
      await updateUserRole(userId, newRole)
      setUsers(prev =>
        prev.map(u => (u.id === userId ? { ...u, role: newRole } : u))
      )
    } catch (err) {
      alert(err.message)
    } finally {
      setActionLoading(null)
    }
  }

  async function handleDelete(userId) {
    if (!window.confirm(t('confirmDeleteUser') || 'Êtes-vous sûr de vouloir supprimer cet utilisateur ?')) {
      return
    }
    try {
      setActionLoading(userId)
      await deleteUser(userId)
      setUsers(prev => prev.filter(u => u.id !== userId))
    } catch (err) {
      alert(err.message)
    } finally {
      setActionLoading(null)
    }
  }

  if (loading) {
    return (
      <div className="admin-loading">
        <div className="spinner"></div>
        <p>{t('loadingUsers') || 'Chargement des utilisateurs...'}</p>
      </div>
    )
  }

  return (
    <div className="admin-container">
      <div className="admin-header">
        <div>
          <h2 className="admin-title">{t('userManagementTitle') || 'Gestion des Utilisateurs'}</h2>
          <p className="admin-subtitle">
            {t('userManagementSubtitle') || 'Validez les inscriptions et gérez les rôles et permissions.'}
          </p>
        </div>
        <button className="btn btn-secondary" onClick={loadUsers}>
          🔄 {t('refresh') || 'Actualiser'}
        </button>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="table-responsive">
        <table className="admin-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Email</th>
              <th>{t('role') || 'Rôle'}</th>
              <th>{t('status') || 'Statut'}</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.length === 0 ? (
              <tr>
                <td colSpan="5" className="text-center text-muted py-4">
                  {t('noUsersFound') || 'Aucun utilisateur trouvé'}
                </td>
              </tr>
            ) : (
              users.map(u => (
                <tr key={u.id}>
                  <td>{u.id}</td>
                  <td className="font-semibold">{u.email}</td>
                  <td>
                    <select
                      className="role-select"
                      value={u.role}
                      onChange={e => handleRoleChange(u.id, e.target.value)}
                      disabled={actionLoading === u.id}
                    >
                      <option value="admin">Admin</option>
                      <option value="analyst">Analyst</option>
                      <option value="viewer">Viewer</option>
                    </select>
                  </td>
                  <td>
                    <span className={`status-badge status-${u.status}`}>
                      {u.status.toUpperCase()}
                    </span>
                  </td>
                  <td>
                    <div className="actions-cell">
                      {u.status === 'pending' && (
                        <>
                          <button
                            className="btn-action btn-approve"
                            onClick={() => handleStatusChange(u.id, 'active')}
                            disabled={actionLoading === u.id}
                            title={t('approve') || 'Approuver'}
                          >
                            ✅
                          </button>
                          <button
                            className="btn-action btn-reject"
                            onClick={() => handleStatusChange(u.id, 'rejected')}
                            disabled={actionLoading === u.id}
                            title={t('reject') || 'Rejeter'}
                          >
                            ❌
                          </button>
                        </>
                      )}
                      {u.status === 'rejected' && (
                        <button
                          className="btn-action btn-approve"
                          onClick={() => handleStatusChange(u.id, 'active')}
                          disabled={actionLoading === u.id}
                          title={t('approve') || 'Approuver'}
                        >
                          ✅ Reactiver
                        </button>
                      )}
                      {u.status === 'active' && (
                        <button
                          className="btn-action btn-reject"
                          onClick={() => handleStatusChange(u.id, 'rejected')}
                          disabled={actionLoading === u.id}
                          title={t('suspend') || 'Suspendre'}
                        >
                          🚫
                        </button>
                      )}
                      <button
                        className="btn-action btn-delete"
                        onClick={() => handleDelete(u.id)}
                        disabled={actionLoading === u.id}
                        title={t('delete') || 'Supprimer'}
                      >
                        🗑️
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
