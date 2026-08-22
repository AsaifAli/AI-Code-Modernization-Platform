"""Hosted-safe sidebar recovery bridge for LegacyLens."""
from __future__ import annotations
import streamlit.components.v1 as components

_TOGGLE_HTML = r"""
<script>
(() => {
  const parentWindow = window.parent;
  const doc = parentWindow.document;
  const RECOVERY_FLAG = "legacylens-sidebar-recovery-v1";

  const recoverPersistedSidebarState = () => {
    try {
      if (parentWindow.sessionStorage.getItem(RECOVERY_FLAG) === "1") return false;
      const staleKeys = [];
      for (let i = 0; i < parentWindow.localStorage.length; i += 1) {
        const key = parentWindow.localStorage.key(i);
        if (key && /sidebar/i.test(key)) staleKeys.push(key);
      }
      parentWindow.sessionStorage.setItem(RECOVERY_FLAG, "1");
      if (staleKeys.length) {
        staleKeys.forEach((key) => parentWindow.localStorage.removeItem(key));
        parentWindow.location.reload();
        return true;
      }
    } catch (_) {}
    return false;
  };

  if (recoverPersistedSidebarState()) return;

  const SELECTORS = [
    '[data-testid="stSidebarCollapsedControl"] button',
    '[data-testid="stSidebarCollapsedControl"]',
    '[data-testid="stSidebarCollapseButton"] button',
    '[data-testid="stSidebarCollapseButton"]',
    '[data-testid="collapsedControl"] button',
    '[data-testid="collapsedControl"]'
  ];
  const findToggle = () => {
    for (const selector of SELECTORS) {
      const el = doc.querySelector(selector);
      if (el) return el;
    }
    return null;
  };
  const isCollapsed = () => {
    const sidebar = doc.querySelector('section[data-testid="stSidebar"]');
    if (sidebar && sidebar.getAttribute('aria-expanded') === 'false') return true;
    if (sidebar && sidebar.getAttribute('aria-expanded') === 'true') return false;
    return !sidebar;
  };
  const BUTTON_ID = 'legacylens-sidebar-reopen';
  const ensureButton = () => {
    let btn = doc.getElementById(BUTTON_ID);
    if (!isCollapsed()) {
      if (btn) btn.style.setProperty('display', 'none', 'important');
      return;
    }
    if (!btn) {
      btn = doc.createElement('button');
      btn.id = BUTTON_ID;
      btn.type = 'button';
      btn.setAttribute('aria-label', 'Open sidebar');
      btn.title = 'Open sidebar';
      btn.innerHTML = '&#8250;';
      btn.addEventListener('click', () => {
        const native = findToggle();
        if (native) native.click(); else parentWindow.location.reload();
      });
      doc.body.appendChild(btn);
    }
    btn.style.setProperty('position', 'fixed', 'important');
    btn.style.setProperty('top', '0.65rem', 'important');
    btn.style.setProperty('left', '0.65rem', 'important');
    btn.style.setProperty('z-index', '999999', 'important');
    btn.style.setProperty('display', 'flex', 'important');
    btn.style.setProperty('align-items', 'center', 'important');
    btn.style.setProperty('justify-content', 'center', 'important');
    btn.style.setProperty('width', '2.2rem', 'important');
    btn.style.setProperty('height', '2.2rem', 'important');
    btn.style.setProperty('border-radius', '0.65rem', 'important');
    const rootStyle = parentWindow.getComputedStyle(doc.documentElement);
    const surface = rootStyle.getPropertyValue('--ui-surface').trim() || 'rgba(17,24,39,.90)';
    const text = rootStyle.getPropertyValue('--ui-text').trim() || '#fff';
    const border = rootStyle.getPropertyValue('--ui-border').trim() || 'rgba(120,120,140,.30)';
    const shadow = rootStyle.getPropertyValue('--ui-shadow').trim() || '0 6px 18px rgba(15,23,42,.22)';
    btn.style.setProperty('border', `1px solid ${border}`, 'important');
    btn.style.setProperty('background', surface, 'important');
    btn.style.setProperty('color', text, 'important');
    btn.style.setProperty('font-size', '1.3rem', 'important');
    btn.style.setProperty('cursor', 'pointer', 'important');
    btn.style.setProperty('box-shadow', shadow, 'important');
    btn.style.setProperty('pointer-events', 'auto', 'important');
  };
  const repairNative = () => {
    SELECTORS.forEach((selector) => {
      const target = doc.querySelector(selector);
      if (!target) return;
      target.style.setProperty('pointer-events', 'auto', 'important');
      target.style.setProperty('z-index', '100001', 'important');
    });
  };
  const tick = () => { repairNative(); ensureButton(); };
  tick();
  window.setInterval(tick, 800);
  try {
    const observer = new MutationObserver(tick);
    observer.observe(doc.documentElement, {attributes:true, attributeFilter:['class','style','data-theme']});
  } catch (_) {}
})();
</script>
"""

def render_sidebar_toggle() -> None:
    components.html(_TOGGLE_HTML, height=1, width=1)
