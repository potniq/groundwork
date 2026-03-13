(function () {
  function getPostHog() {
    if (typeof window === 'undefined') {
      return null;
    }

    const candidate = window.posthog;
    if (!candidate || typeof candidate.capture !== 'function') {
      return null;
    }

    return candidate;
  }

  function getContext() {
    if (typeof window === 'undefined') {
      return {};
    }

    const context = window.GROUNDWORK_ANALYTICS_CONTEXT;
    if (!context || typeof context !== 'object') {
      return {};
    }

    return context;
  }

  function getSuperProperties() {
    if (typeof window === 'undefined') {
      return {};
    }

    const properties = window.GROUNDWORK_ANALYTICS_SUPER_PROPERTIES;
    if (!properties || typeof properties !== 'object') {
      return {};
    }

    return properties;
  }

  function getResetProperties() {
    if (typeof window === 'undefined') {
      return [];
    }

    const properties = window.GROUNDWORK_ANALYTICS_RESET_PROPERTIES;
    return Array.isArray(properties) ? properties : [];
  }

  function cleanProperties(properties) {
    const cleaned = {};

    Object.entries(properties || {}).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') {
        return;
      }

      cleaned[key] = value;
    });

    return cleaned;
  }

  function writeConsole(level, message, properties) {
    const details = cleanProperties(properties);
    const consoleMethod =
      level === 'error' ? console.error : level === 'warn' || level === 'warning' ? console.warn : console.info;

    if (Object.keys(details).length > 0) {
      consoleMethod(`[Groundwork analytics] ${message}`, details);
      return;
    }

    consoleMethod(`[Groundwork analytics] ${message}`);
  }

  function sendEvent(eventName, properties) {
    const posthog = getPostHog();
    if (!posthog || !eventName) {
      return;
    }

    posthog.capture(eventName, cleanProperties({ ...getContext(), ...properties }));
  }

  function capture(eventName, properties) {
    if (!eventName) {
      return;
    }

    writeConsole('info', `Captured ${eventName}`, properties);
    sendEvent(eventName, properties);
  }

  function log(level, message, properties) {
    writeConsole(level, message, properties);
    sendEvent('client_log', {
      log_level: level,
      message,
      ...properties,
    });
  }

  function captureException(error, properties) {
    const normalizedError = error instanceof Error ? error : new Error(String(error));
    const posthog = getPostHog();

    writeConsole('error', normalizedError.message, properties);

    if (!posthog || typeof posthog.captureException !== 'function') {
      sendEvent('client_exception', {
        message: normalizedError.message,
        ...properties,
      });
      return;
    }

    posthog.captureException(normalizedError, cleanProperties({ ...getContext(), ...properties }));
  }

  function syncSuperProperties() {
    const posthog = getPostHog();
    if (!posthog) {
      return;
    }

    getResetProperties().forEach((propertyName) => {
      if (typeof propertyName === 'string' && propertyName) {
        posthog.unregister(propertyName);
      }
    });

    const superProperties = cleanProperties(getSuperProperties());
    if (Object.keys(superProperties).length > 0) {
      posthog.register(superProperties);
      writeConsole('info', 'Registered PostHog super properties', superProperties);
    }
  }

  function parseProperties(element) {
    const raw = element.getAttribute('data-analytics-props');
    if (!raw) {
      return {};
    }

    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch (_) {
      return {};
    }
  }

  function attachTrackedClicks() {
    document.addEventListener('click', (event) => {
      if (!(event.target instanceof Element)) {
        return;
      }

      const trackedElement = event.target.closest('[data-analytics-event]');
      if (!trackedElement) {
        return;
      }

      const eventName = trackedElement.getAttribute('data-analytics-event');
      const properties = parseProperties(trackedElement);

      if (trackedElement instanceof HTMLAnchorElement) {
        try {
          const url = new URL(trackedElement.href, window.location.origin);
          properties.link_host = url.host;
          properties.is_external = url.origin !== window.location.origin;
        } catch (_) {
          // Ignore malformed URLs and capture the explicit properties only.
        }
      }

      capture(eventName, properties);
    });
  }

  function attachSectionObserver(selector, eventName) {
    if (typeof window === 'undefined' || !('IntersectionObserver' in window)) {
      return;
    }

    const sections = Array.from(document.querySelectorAll(selector));
    if (!sections.length) {
      return;
    }

    const seenSections = new Set();
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting || entry.intersectionRatio < 0.6) {
            return;
          }

          const section = entry.target;
          const sectionName = section.getAttribute('data-analytics-section');
          if (!sectionName || seenSections.has(sectionName)) {
            return;
          }

          seenSections.add(sectionName);
          capture(eventName || 'guide_section_viewed', { section_name: sectionName });
          observer.unobserve(section);
        });
      },
      { threshold: [0.6] },
    );

    sections.forEach((section) => observer.observe(section));
  }

  function debounce(callback, delayMs) {
    let timeoutId = null;

    return (...args) => {
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }

      timeoutId = window.setTimeout(() => {
        callback(...args);
      }, delayMs);
    };
  }

  window.groundworkAnalytics = {
    attachSectionObserver,
    capture,
    captureException,
    debounce,
    log,
    syncSuperProperties,
  };

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      () => {
        syncSuperProperties();
        attachTrackedClicks();
      },
      { once: true },
    );
  } else {
    syncSuperProperties();
    attachTrackedClicks();
  }
})();
