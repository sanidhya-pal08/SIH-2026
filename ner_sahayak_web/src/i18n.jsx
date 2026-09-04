import React, { createContext, useContext, useState, useMemo } from 'react';

const translations = {
  en: {
    "app.title": "NER Sahayak",
    "nav.dashboard": "Dashboard",
    "nav.dispatch": "Dispatch",
    "nav.alerts": "Alerts & Escalation",
    "nav.audit": "Audit Timeline",
    "nav.logout": "Logout",
    "alert.title": "Alerts",
    "alert.acknowledge": "Acknowledge",
    "alert.escalate": "Escalate to Air",
    "audit.title": "Audit Timeline",
    "audit.verified": "Verified",
    "audit.invalid": "Tampered",
  },
  hi: {
    "app.title": "NER सहायक",
    "nav.dashboard": "डैशबोर्ड",
    "nav.dispatch": "डिस्पैच",
    "nav.alerts": "अलर्ट और एस्केलेशन",
    "nav.audit": "ऑडिट टाइमलाइन",
    "nav.logout": "लॉग आउट",
    "alert.title": "अलर्ट",
    "alert.acknowledge": "स्वीकार करें",
    "alert.escalate": "एयर के लिए एस्केलेट करें",
    "audit.title": "ऑडिट टाइमलाइन",
    "audit.verified": "सत्यापित",
    "audit.invalid": "छेड़छाड़",
  }
};

const I18nContext = createContext();

export const I18nProvider = ({ children }) => {
  const [lang, setLang] = useState('en');

  const t = (key) => {
    return translations[lang]?.[key] || translations['en'][key] || key;
  };

  const value = useMemo(() => ({ lang, setLang, t }), [lang]);

  return (
    <I18nContext.Provider value={value}>
      {children}
    </I18nContext.Provider>
  );
};

export const useTranslation = () => useContext(I18nContext);
