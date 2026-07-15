import { createContext, useContext, useState, useEffect, useMemo, useCallback } from 'react'

const LanguageContext = createContext()

const translations = {
  fr: {
    // Navbar
    navAnalyze: 'Analyser',
    navHistory: 'Historique',
    navDashboard: 'Dashboard',
    navAnalyzing: 'Analyse…',
    navLightMode: 'Passer en thème clair',
    navDarkMode: 'Passer en thème sombre',
    navNotifications: 'Notifications',
    navMarkAllRead: 'Tout marquer lu',
    navNoNotifications: 'Aucune notification',
    navMyAccount: 'Mon compte',
    navSettings: 'Paramètres',
    navLogout: 'Se déconnecter',
    navAdmin: 'admin',
    navAnalyst: 'analyst',
    navViewer: 'viewer',
    navLastLogin: 'Dernière connexion :',

    // Relative dates
    dateJustNow: 'à l\'instant',
    dateMinsAgo: 'il y a {n} min',
    dateHoursAgo: 'il y a {n}h',
    dateDaysAgo: 'il y a {n} j',

    // Modals
    modalClose: '✕',
    accountTitle: 'Mon compte',
    accountEmail: 'Adresse email',
    accountRole: 'Rôle utilisateur',
    accountUserId: 'ID Utilisateur',
    accountOrgId: 'ID Organisation',
    accountPermissions: 'Permissions du rôle',
    roleDescAdmin: 'Accès Administrateur : Vous possédez tous les droits d\'administration, y compris l\'analyse de logs, l\'export PDF, la réanalyse et la suppression des entrées d\'historique.',
    roleDescAnalyst: 'Accès Analyste : Vous pouvez téléverser des fichiers de logs pour analyse, réanalyser les logs existants et exporter les rapports au format PDF.',
    roleDescViewer: 'Accès Lecteur : Vous avez des permissions de lecture seule. Vous pouvez consulter l\'historique et les détails des analyses existantes.',

    settingsTitle: 'Paramètres',
    settingsTheme: 'Thème d\'affichage',
    settingsThemeDesc: 'Basculez entre le mode sombre et le mode clair',
    settingsThemeLightBtn: '☀️ Clair',
    settingsThemeDarkBtn: '🌙 Sombre',
    settingsModel: 'Modèle d\'analyse',
    settingsModelDesc: 'Moteur IA utilisé pour la détection et la résolution',
    settingsData: 'Données locales',
    settingsDataDesc: 'Effacer la session et les préférences stockées',
    settingsResetBtn: 'Réinitialiser',
    settingsResetConfirm: 'Êtes-vous sûr de vouloir réinitialiser vos données locales ? Vous serez déconnecté.',
    settingsVersion: 'Version de l\'application',

    // Login Page
    loginWelcomeJoin: 'Rejoignez la plateforme d\'analyse intelligente de logs.',
    loginWelcomeConnect: 'Connectez-vous pour analyser vos fichiers de logs.',
    loginEmailLabel: 'Adresse email',
    loginPasswordLabel: 'Mot de passe',
    loginOrgNameLabel: 'Nom de l\'organisation',
    loginOrgSlugLabel: 'Slug de l\'organisation',
    loginDesiredRole: 'Rôle souhaité',
    loginRoleViewer: 'Lecteur (Consultation seule)',
    loginRoleAnalyst: 'Analyste (Analyse + Export PDF)',
    loginRoleAdmin: 'Administrateur (Tous droits)',
    loginLoading: 'Traitement en cours...',
    loginBtnSubmitRegister: "S'inscrire",
    loginBtnSubmitLogin: 'Se connecter',
    loginToggleHaveAccount: 'Vous avez déjà un compte ? Connectez-vous',
    loginToggleNewAccount: 'Nouveau ? Créez une organisation et inscrivez-vous',
    loginOrgError: 'Le nom et le slug de l\'organisation sont obligatoires.',

    // Log Uploader
    uploaderTitle: 'Uploader un fichier log',
    uploaderDropText: 'Déposer un fichier .log ou .txt',
    uploaderClickText: 'ou cliquer pour sélectionner un fichier',
    uploaderReadyText: '{name} prêt pour l\'analyse',
    uploaderViewerTitle: 'Consultation seule',
    uploaderViewerDesc: 'Sélectionnez un historique à gauche',
    uploaderBtnRemove: '❌ Retirer',
    uploaderBtnChange: '🔄 Changer de fichier',
    uploaderBtnLoading: 'Analyse en cours...',
    uploaderBtnAnalyze: 'Analyser avec IA',
    uploaderRoleViewerLabel: 'Lecture seule (Rôle Lecteur)',
    uploaderHint: 'Le backend détectera les lignes ERROR, WARNING, FATAL et EXCEPTION.',
    uploaderRoleError: 'Rôle Lecteur : Vous n\'avez pas l\'autorisation d\'uploader des logs.',
    uploaderFormatError: 'Format non supporté. Choisis un fichier .log ou .txt.',

    // History Page
    historyPageTitle: 'Historique des Analyses',
    historyPageSubtitle: 'Retrouvez et réouvrez toutes vos analyses passées',
    historyStatAnalyses: 'Analyses',
    historyStatFiles: 'Fichiers',
    historyStatErrors: 'Erreurs totales',
    historySearchPlaceholder: 'Rechercher un fichier, un ID…',
    historySortRecent: 'Plus récent',
    historySortOldest: 'Plus ancien',
    historySortErrorsDesc: 'Plus d\'erreurs',
    historySortErrorsAsc: 'Moins d\'erreurs',
    historyViewTooltipGrouped: 'Vue groupée',
    historyViewTooltipFlat: 'Vue liste',
    historyLoading: 'Chargement de l\'historique…',
    historyEmptyState: 'Aucune analyse enregistrée pour l\'instant.',
    historyNoResults: 'Aucun résultat pour cette recherche.',
    historyClearSearch: 'Effacer la recherche',
    historyRunsCount: '{n} analyse{s}',
    historyLatestAnalysis: 'Dernière analyse : {date} · {errors} erreurs au total',
    historyErrorLabel: 'erreur{s}',

    // Error Analysis Page
    analysisResultTitle: 'Résultat : {name}',
    analysisResultDesc: 'Analyse IA structurée en explication, causes et solutions.',
    analysisBtnExport: 'Exporter PDF',
    analysisStatDetected: 'Détectées',
    analysisStatAnalyzed: 'Analysées',
    analysisStatSkipped: 'Ignorées',
    analysisCardTitle: 'Erreur #{n}',
    analysisLineLabel: 'Ligne {n}',
    analysisFailed: 'Analyse IA échouée : {err}',
    analysisExplanationHeader: 'Explication',
    analysisCausesHeader: 'Causes possibles',
    analysisSolutionsHeader: 'Solutions recommandées',

    // Dashboard Page
    dashTitle: 'Dashboard',
    dashSubtitle: 'Vue d\'ensemble de vos analyses de logs',
    dashBackBtn: 'Retour à l\'analyse',
    dashLoading: 'Chargement des statistiques…',
    dashTotalAnalyses: 'Analyses totales',
    dashTotalAnalysesSub: 'depuis le début',
    dashErrorsDetected: 'Erreurs détectées',
    dashErrorsDetectedSub: '{n} analysées par l\'IA',
    dashAiRate: 'Taux d\'analyse IA',
    dashAiRateSub: 'erreurs analysées / détectées',
    dashUniqueFiles: 'Fichiers uniques',
    dashUniqueFilesSub: 'dans le top 5',
    dashChartAnalysesDay: '📅 Analyses par jour (7 derniers jours)',
    dashChartErrorsDay: '🔴 Erreurs par jour (7 derniers jours)',
    dashChartErrorsLevel: '🎯 Erreurs par niveau',
    dashChartErrorsCategory: '🏷️ Catégories d\'erreurs',
    dashChartTopFiles: '📁 Top fichiers analysés',
    dashEmptyChart: 'Aucune donnée',
    dashEmptyChartDays: 'Aucune donnée pour les 7 derniers jours',
    dashTableRank: '#',
    dashTableFile: 'Fichier',
    dashTableRuns: 'Runs',
    dashTableErrors: 'Erreurs',
    dashTableSplit: 'Répartition',

    // User Management
    navUsers: 'Utilisateurs',
    confirmDeleteUser: 'Êtes-vous sûr de vouloir supprimer cet utilisateur ?',
    loadingUsers: 'Chargement des utilisateurs...',
    userManagementTitle: 'Gestion des Utilisateurs',
    userManagementSubtitle: 'Validez les inscriptions et gerez les rôles et permissions.',
    noUsersFound: 'Aucun utilisateur trouvé',
    approve: 'Approuver',
    reject: 'Rejeter',
    suspend: 'Suspendre',
    delete: 'Supprimer',
    role: 'Rôle',
    status: 'Statut',
    refresh: 'Actualiser',
  },
  en: {
    // Navbar
    navAnalyze: 'Analyze',
    navHistory: 'History',
    navDashboard: 'Dashboard',
    navAnalyzing: 'Analyzing…',
    navLightMode: 'Switch to light theme',
    navDarkMode: 'Switch to dark theme',
    navNotifications: 'Notifications',
    navMarkAllRead: 'Mark all as read',
    navNoNotifications: 'No notifications',
    navMyAccount: 'My Account',
    navSettings: 'Settings',
    navLogout: 'Sign Out',
    navAdmin: 'admin',
    navAnalyst: 'analyst',
    navViewer: 'viewer',
    navLastLogin: 'Last login:',

    // Relative dates
    dateJustNow: 'just now',
    dateMinsAgo: '{n} min ago',
    dateHoursAgo: '{n}h ago',
    dateDaysAgo: '{n} d ago',

    // Modals
    modalClose: '✕',
    accountTitle: 'My Account',
    accountEmail: 'Email Address',
    accountRole: 'User Role',
    accountUserId: 'User ID',
    accountOrgId: 'Org ID',
    accountPermissions: 'Role Permissions',
    roleDescAdmin: 'Admin Access: You possess all administrative rights, including log analysis, PDF export, re-analysis, and history deletion.',
    roleDescAnalyst: 'Analyst Access: You can upload log files for analysis, re-analyze existing logs, and export PDF reports.',
    roleDescViewer: 'Viewer Access: You have read-only permissions. You can view the history list and details of existing analyses.',

    settingsTitle: 'Settings',
    settingsTheme: 'Theme Mode',
    settingsThemeDesc: 'Toggle between dark and light themes',
    settingsThemeLightBtn: '☀️ Light',
    settingsThemeDarkBtn: '🌙 Dark',
    settingsModel: 'Analysis Model',
    settingsModelDesc: 'AI engine used for detection and resolution',
    settingsData: 'Local Data',
    settingsDataDesc: 'Clear session data and stored preferences',
    settingsResetBtn: 'Reset',
    settingsResetConfirm: 'Are you sure you want to reset your local data? You will be signed out.',
    settingsVersion: 'App Version',

    // Login Page
    loginWelcomeJoin: 'Join the smart log analysis platform.',
    loginWelcomeConnect: 'Sign in to analyze your log files.',
    loginEmailLabel: 'Email Address',
    loginPasswordLabel: 'Password',
    loginOrgNameLabel: 'Organization Name',
    loginOrgSlugLabel: 'Organization Slug',
    loginDesiredRole: 'Desired Role',
    loginRoleViewer: 'Viewer (Read-only)',
    loginRoleAnalyst: 'Analyst (Analysis + PDF Export)',
    loginRoleAdmin: 'Administrator (All rights)',
    loginLoading: 'Processing...',
    loginBtnSubmitRegister: 'Register',
    loginBtnSubmitLogin: 'Sign In',
    loginToggleHaveAccount: 'Already have an account? Sign in',
    loginToggleNewAccount: 'New here? Create an organization and register',
    loginOrgError: 'Organization name and slug are required.',

    // Log Uploader
    uploaderTitle: 'Upload a log file',
    uploaderDropText: 'Drop a .log or .txt file here',
    uploaderClickText: 'or click to select a file',
    uploaderReadyText: '{name} ready for analysis',
    uploaderViewerTitle: 'Read-only',
    uploaderViewerDesc: 'Select an analysis from the history',
    uploaderBtnRemove: '❌ Remove',
    uploaderBtnChange: '🔄 Change file',
    uploaderBtnLoading: 'Analyzing...',
    uploaderBtnAnalyze: 'Analyze with AI',
    uploaderRoleViewerLabel: 'Read-only (Viewer)',
    uploaderHint: 'The backend will detect ERROR, WARNING, FATAL, and EXCEPTION lines.',
    uploaderRoleError: 'Viewer Role: You do not have permission to upload logs.',
    uploaderFormatError: 'Unsupported format. Choose a .log or .txt file.',

    // History Page
    historyPageTitle: 'Analysis History',
    historyPageSubtitle: 'View and reopen all your past analyses',
    historyStatAnalyses: 'Analyses',
    historyStatFiles: 'Files',
    historyStatErrors: 'Total Errors',
    historySearchPlaceholder: 'Search file name, ID…',
    historySortRecent: 'Most recent',
    historySortOldest: 'Oldest first',
    historySortErrorsDesc: 'Most errors',
    historySortErrorsAsc: 'Least errors',
    historyViewTooltipGrouped: 'Grouped view',
    historyViewTooltipFlat: 'List view',
    historyLoading: 'Loading history…',
    historyEmptyState: 'No analyses saved yet.',
    historyNoResults: 'No results found for this search.',
    historyClearSearch: 'Clear search',
    historyRunsCount: '{n} run{s}',
    historyLatestAnalysis: 'Latest analysis: {date} · {errors} errors total',
    historyErrorLabel: 'error{s}',

    // Error Analysis Page
    analysisResultTitle: 'Result: {name}',
    analysisResultDesc: 'Structured AI analysis with explanation, causes, and solutions.',
    analysisBtnExport: 'Export PDF',
    analysisStatDetected: 'Detected',
    analysisStatAnalyzed: 'Analyzed',
    analysisStatSkipped: 'Skipped',
    analysisCardTitle: 'Error #{n}',
    analysisLineLabel: 'Line {n}',
    analysisFailed: 'AI Analysis failed: {err}',
    analysisExplanationHeader: 'Explanation',
    analysisCausesHeader: 'Potential Causes',
    analysisSolutionsHeader: 'Recommended Solutions',

    // Dashboard Page
    dashTitle: 'Dashboard',
    dashSubtitle: 'Overview of your log analyses',
    dashBackBtn: 'Back to analysis',
    dashLoading: 'Loading statistics…',
    dashTotalAnalyses: 'Total Analyses',
    dashTotalAnalysesSub: 'since the beginning',
    dashErrorsDetected: 'Errors Detected',
    dashErrorsDetectedSub: '{n} analyzed by AI',
    dashAiRate: 'AI Analysis Rate',
    dashAiRateSub: 'analyzed / detected errors',
    dashUniqueFiles: 'Unique Files',
    dashUniqueFilesSub: 'in the top 5',
    dashChartAnalysesDay: '📅 Analyses per day (last 7 days)',
    dashChartErrorsDay: '🔴 Errors per day (last 7 days)',
    dashChartErrorsLevel: '🎯 Errors by level',
    dashChartErrorsCategory: '🏷️ Error categories',
    dashChartTopFiles: '📁 Top analyzed files',
    dashEmptyChart: 'No data',
    dashEmptyChartDays: 'No data for the last 7 days',
    dashTableRank: '#',
    dashTableFile: 'File',
    dashTableRuns: 'Runs',
    dashTableErrors: 'Errors',
    dashTableSplit: 'Distribution',

    // User Management
    navUsers: 'Users',
    confirmDeleteUser: 'Are you sure you want to delete this user?',
    loadingUsers: 'Loading users...',
    userManagementTitle: 'User Management',
    userManagementSubtitle: 'Approve registrations and manage user roles and permissions.',
    noUsersFound: 'No users found',
    approve: 'Approve',
    reject: 'Reject',
    suspend: 'Suspend',
    delete: 'Delete',
    role: 'Role',
    status: 'Status',
    refresh: 'Refresh',
  }
}

export function LanguageProvider({ children }) {
  const [language, setLanguage] = useState(() => {
    return localStorage.getItem('lang') || 'fr'
  })

  useEffect(() => {
    localStorage.setItem('lang', language)
  }, [language])

  const t = useCallback((key, params = {}) => {
    const dict = translations[language] || translations.fr
    let text = dict[key] || translations.fr[key] || key

    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(`{${k}}`, v)
    })

    return text
  }, [language])

  const value = useMemo(
    () => ({ language, setLanguage, t }),
    [language, t]
  )

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useTranslation() {
  const context = useContext(LanguageContext)
  if (!context) {
    throw new Error('useTranslation must be used within a LanguageProvider')
  }
  return context
}
