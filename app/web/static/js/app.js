/**
 * Task Assistant Agent - Main Coordinator (Entry Point)
 * Boots up modular features and triggers initial data hydration.
 */

document.addEventListener('DOMContentLoaded', () => {
  console.log('🤖 Task Assistant Agent Frontend Initializing...');

  // Initialize event listeners across modules
  if (window.initNavigation) window.initNavigation();
  if (window.initSettingsModal) window.initSettingsModal();
  if (window.initChat) window.initChat();
  if (window.initKanban) window.initKanban();
  if (window.initRag) window.initRag();
  if (window.initMonitoring) window.initMonitoring();

  // Initial startup data hydration
  if (window.loadSettings) window.loadSettings();
  if (window.loadChatHistory) window.loadChatHistory();
  if (window.loadTasks) window.loadTasks();
  if (window.loadDailyNotes) window.loadDailyNotes();
  if (window.loadDocs) window.loadDocs();
  if (window.projectsManager && window.projectsManager.loadProjects) window.projectsManager.loadProjects();
  if (window.loadMonitoring) window.loadMonitoring();

  console.log('✓ Task Assistant Agent Frontend Ready.');
});
