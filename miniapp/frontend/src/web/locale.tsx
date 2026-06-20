import React, { createContext, useContext, useState } from "react";

export type Lang = "en" | "ru";

const STORAGE_KEY = "web_lang";

function savedLang(): Lang {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === "ru" || v === "en") return v;
  } catch {}
  return "en";
}

export interface Translations {
  lang_toggle: string;
  // Sidebar / header
  menu_subscription: string;
  menu_buy: string;
  menu_devices: string;
  menu_settings: string;
  btn_logout: string;
  header_portal: string;
  // Register
  reg_title: string;
  reg_subtitle: string;
  invite_label: string;
  invite_placeholder: string;
  invite_checking: string;
  invite_invalid: string;
  invite_valid: string;
  discount_accepted: string;
  discount_text: (pct: number) => string;
  pwd_label: string;
  pwd_placeholder: string;
  confirm_label: string;
  confirm_placeholder: string;
  btn_create: string;
  have_account: string;
  sign_in: string;
  err_email_taken: string;
  err_invalid_invite: string;
  err_rate_limited: string;
  err_req_invite: string;
  err_reg: string;
  err_network: string;
  val_email_req: string;
  val_email_format: string;
  val_pwd_req: string;
  val_pwd_min: string;
  val_confirm_req: string;
  val_confirm_match: string;
  val_invite_req: string;
  // Subscription tab
  sub_title: string;
  btn_refresh: string;
  no_sub_title: string;
  no_sub_text: string;
  btn_buy_sub: string;
  err_load_sub: string;
  label_plan: string;
  label_status: string;
  label_days_left: string;
  label_expires: string;
  label_devices: string;
  label_traffic: string;
  traffic_unlimited: string;
  traffic_usage: string;
  copy_sub_link: string;
  status_active: string;
  status_expired: string;
  status_disabled: string;
  status_limited: string;
  // Buy tab
  buy_title: string;
  promo_active: string;
  promo_applied: (pct: number) => string;
  no_tariffs: string;
  btn_pay: string;
  err_load_plans: string;
  invoice_title: string;
  to_pay: string;
  without_discount: string;
  btn_proceed: string;
  err_rate_limited_inv: string;
  err_provider: string;
  err_not_verified: string;
  err_invoice: string;
  btn_back: string;
  discount_applied_msg: (pct: number) => string;
  days: (n: number) => string;
  // Devices tab
  dev_title: string;
  err_load_dev: string;
  err_remove_dev: string;
  err_rate_limited_dev: string;
  col_device: string;
  col_platform: string;
  col_added: string;
  unknown_device: string;
  no_devices: string;
  dev_auto_registered: string;
  confirm_remove: string;
  confirm_remove_desc: string;
  ok_remove: string;
  cancel: string;
  // Settings tab
  settings_title: string;
  card_account: string;
  card_password: string;
  card_security: string;
  label_email_status: string;
  label_telegram: string;
  status_verified: string;
  status_not_verified: string;
  btn_verify: string;
  tg_linked: string;
  tg_not_linked: string;
  pwd_current: string;
  pwd_new: string;
  pwd_confirm_field: string;
  val_pwd_current_req: string;
  val_pwd_new_req: string;
  val_pwd_new_min: string;
  val_pwd_confirm_req: string;
  val_pwd_confirm_match: string;
  btn_change_pwd: string;
  btn_revoke_sessions: string;
  btn_logout_settings: string;
  confirm_revoke_title: string;
  confirm_revoke_content: string;
  ok_revoke: string;
  revoke_security_note: string;
  err_wrong_pwd: string;
  err_rate_limited_pwd: string;
  msg_pwd_changed: string;
  msg_sessions_revoked: string;
  err_revoke_sessions: string;
  msg_code_sent: string;
  err_send_code: string;
  err_change_pwd: string;
}

const en: Translations = {
  lang_toggle: "RU",
  menu_subscription: "Subscription",
  menu_buy: "Buy",
  menu_devices: "Devices",
  menu_settings: "Settings",
  btn_logout: "Sign Out",
  header_portal: "Client Portal",
  reg_title: "Create Account",
  reg_subtitle: "An invitation code is required to register",
  invite_label: "Invitation Code",
  invite_placeholder: "e.g. ABCD1234",
  invite_checking: "Checking code…",
  invite_invalid: "Invalid code",
  invite_valid: "Code accepted",
  discount_accepted: "Code accepted!",
  discount_text: (pct) => `${pct}% discount on first payment`,
  pwd_label: "Password",
  pwd_placeholder: "At least 8 characters",
  confirm_label: "Confirm Password",
  confirm_placeholder: "Repeat your password",
  btn_create: "Create Account",
  have_account: "Already have an account?",
  sign_in: "Sign in",
  err_email_taken: "This email is already registered",
  err_invalid_invite: "Invalid invitation code",
  err_rate_limited: "Too many attempts. Please wait",
  err_req_invite: "Enter a valid invitation code",
  err_reg: "Registration failed. Please try again.",
  err_network: "Network error. Check your connection.",
  val_email_req: "Enter your email",
  val_email_format: "Invalid email address",
  val_pwd_req: "Enter a password",
  val_pwd_min: "At least 8 characters",
  val_confirm_req: "Repeat your password",
  val_confirm_match: "Passwords do not match",
  val_invite_req: "Enter your invitation code",
  sub_title: "My Subscription",
  btn_refresh: "Refresh",
  no_sub_title: "No active subscription",
  no_sub_text: "Choose a plan to get started",
  btn_buy_sub: "Buy Subscription",
  err_load_sub: "Failed to load subscription data",
  label_plan: "Plan",
  label_status: "Status",
  label_days_left: "Days left",
  label_expires: "Expires",
  label_devices: "Devices",
  label_traffic: "Traffic",
  traffic_unlimited: "Unlimited traffic",
  traffic_usage: "Traffic usage",
  copy_sub_link: "Copy subscription link",
  status_active: "Active",
  status_expired: "Expired",
  status_disabled: "Disabled",
  status_limited: "Limited",
  buy_title: "Buy Subscription",
  promo_active: "Promo code active:",
  promo_applied: (pct) => `${pct}% discount applied to prices`,
  no_tariffs: "No plans configured",
  btn_pay: "Pay",
  err_load_plans: "Failed to load plans. Try again.",
  invoice_title: "Payment Invoice",
  to_pay: "To pay:",
  without_discount: "Without discount:",
  btn_proceed: "Proceed to Payment",
  err_rate_limited_inv: "Too many requests",
  err_provider: "Payment provider unavailable",
  err_not_verified: "Please verify your email first",
  err_invoice: "Failed to create invoice. Try again.",
  btn_back: "Back",
  discount_applied_msg: (pct) => `${pct}% discount applied`,
  days: (n) => `${n} day${n !== 1 ? "s" : ""}`,
  dev_title: "Devices",
  err_load_dev: "Failed to load devices",
  err_remove_dev: "Failed to remove device",
  err_rate_limited_dev: "Too many requests",
  col_device: "Device",
  col_platform: "Platform",
  col_added: "Added",
  unknown_device: "Unknown device",
  no_devices: "No connected devices",
  dev_auto_registered: "Devices are registered automatically when using the client app.",
  confirm_remove: "Remove device?",
  confirm_remove_desc: "This will disconnect the device from VPN",
  ok_remove: "Remove",
  cancel: "Cancel",
  settings_title: "Account Settings",
  card_account: "Account",
  card_password: "Change Password",
  card_security: "Security",
  label_email_status: "Email status",
  label_telegram: "Telegram",
  status_verified: "Verified",
  status_not_verified: "Not verified",
  btn_verify: "Verify",
  tg_linked: "Linked",
  tg_not_linked: "Not linked",
  pwd_current: "Current password",
  pwd_new: "New password",
  pwd_confirm_field: "Confirm password",
  val_pwd_current_req: "Enter your current password",
  val_pwd_new_req: "Enter a new password",
  val_pwd_new_min: "At least 8 characters",
  val_pwd_confirm_req: "Repeat your password",
  val_pwd_confirm_match: "Passwords do not match",
  btn_change_pwd: "Change Password",
  btn_revoke_sessions: "Sign Out All Devices",
  btn_logout_settings: "Sign Out",
  confirm_revoke_title: "Sign out all sessions?",
  confirm_revoke_content: "All devices will be signed out and re-login will be required.",
  ok_revoke: "Sign Out All",
  revoke_security_note: '"Sign Out All Devices" revokes all refresh tokens and signs out on all devices.',
  err_wrong_pwd: "Incorrect current password",
  err_rate_limited_pwd: "Too many attempts",
  msg_pwd_changed: "Password changed. Please sign in again.",
  msg_sessions_revoked: "All sessions signed out",
  err_revoke_sessions: "Failed to sign out sessions",
  msg_code_sent: "Code sent to your email",
  err_send_code: "Failed to send code",
  err_change_pwd: "Failed to change password",
};

const ru: Translations = {
  lang_toggle: "EN",
  menu_subscription: "Подписка",
  menu_buy: "Купить",
  menu_devices: "Устройства",
  menu_settings: "Настройки",
  btn_logout: "Выйти",
  header_portal: "Клиентский портал",
  reg_title: "Регистрация",
  reg_subtitle: "Для регистрации необходим код приглашения",
  invite_label: "Код приглашения",
  invite_placeholder: "Например: ABCD1234",
  invite_checking: "Проверка кода…",
  invite_invalid: "Недействительный код",
  invite_valid: "Код действителен",
  discount_accepted: "Код принят!",
  discount_text: (pct) => `Скидка ${pct}% на первую оплату`,
  pwd_label: "Пароль",
  pwd_placeholder: "Минимум 8 символов",
  confirm_label: "Повтор пароля",
  confirm_placeholder: "Повторите пароль",
  btn_create: "Создать аккаунт",
  have_account: "Уже есть аккаунт?",
  sign_in: "Войти",
  err_email_taken: "Этот email уже зарегистрирован",
  err_invalid_invite: "Код приглашения недействителен",
  err_rate_limited: "Слишком много попыток. Подождите и попробуйте снова",
  err_req_invite: "Введите действительный код приглашения",
  err_reg: "Ошибка регистрации. Попробуйте снова.",
  err_network: "Ошибка сети. Проверьте соединение.",
  val_email_req: "Введите email",
  val_email_format: "Некорректный email",
  val_pwd_req: "Введите пароль",
  val_pwd_min: "Минимум 8 символов",
  val_confirm_req: "Повторите пароль",
  val_confirm_match: "Пароли не совпадают",
  val_invite_req: "Введите код приглашения",
  sub_title: "Моя подписка",
  btn_refresh: "Обновить",
  no_sub_title: "Нет активной подписки",
  no_sub_text: "Выберите тарифный план для начала работы",
  btn_buy_sub: "Купить подписку",
  err_load_sub: "Не удалось загрузить данные подписки",
  label_plan: "Тариф",
  label_status: "Статус",
  label_days_left: "Осталось дней",
  label_expires: "Действует до",
  label_devices: "Устройств",
  label_traffic: "Трафик",
  traffic_unlimited: "Безлимитный трафик",
  traffic_usage: "Использование трафика",
  copy_sub_link: "Скопировать ссылку подписки",
  status_active: "Активна",
  status_expired: "Истекла",
  status_disabled: "Отключена",
  status_limited: "Ограничена",
  buy_title: "Купить подписку",
  promo_active: "Промокод активен:",
  promo_applied: (pct) => `Скидка ${pct}% применена к ценам`,
  no_tariffs: "Тарифы не настроены",
  btn_pay: "Оплатить",
  err_load_plans: "Не удалось загрузить тарифы. Попробуйте позже.",
  invoice_title: "Счёт на оплату",
  to_pay: "К оплате:",
  without_discount: "Без скидки:",
  btn_proceed: "Перейти к оплате",
  err_rate_limited_inv: "Слишком много запросов",
  err_provider: "Платёжный провайдер недоступен",
  err_not_verified: "Сначала подтвердите email",
  err_invoice: "Ошибка создания счёта. Попробуйте позже.",
  btn_back: "Назад",
  discount_applied_msg: (pct) => `Скидка ${pct}% применена`,
  days: (n) => {
    if (n === 1) return "1 день";
    if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20)) return `${n} дня`;
    return `${n} дней`;
  },
  dev_title: "Устройства",
  err_load_dev: "Не удалось загрузить устройства",
  err_remove_dev: "Не удалось удалить устройство",
  err_rate_limited_dev: "Слишком много запросов",
  col_device: "Устройство",
  col_platform: "Платформа",
  col_added: "Добавлено",
  unknown_device: "Неизвестное устройство",
  no_devices: "Нет подключённых устройств",
  dev_auto_registered: "Устройства регистрируются автоматически при использовании клиентского приложения.",
  confirm_remove: "Удалить устройство?",
  confirm_remove_desc: "Отключит это устройство от VPN",
  ok_remove: "Удалить",
  cancel: "Отмена",
  settings_title: "Настройки аккаунта",
  card_account: "Аккаунт",
  card_password: "Смена пароля",
  card_security: "Безопасность",
  label_email_status: "Статус email",
  label_telegram: "Telegram",
  status_verified: "Подтверждён",
  status_not_verified: "Не подтверждён",
  btn_verify: "Подтвердить",
  tg_linked: "Привязан",
  tg_not_linked: "Не привязан",
  pwd_current: "Текущий пароль",
  pwd_new: "Новый пароль",
  pwd_confirm_field: "Повтор пароля",
  val_pwd_current_req: "Введите текущий пароль",
  val_pwd_new_req: "Введите новый пароль",
  val_pwd_new_min: "Минимум 8 символов",
  val_pwd_confirm_req: "Повторите пароль",
  val_pwd_confirm_match: "Пароли не совпадают",
  btn_change_pwd: "Сменить пароль",
  btn_revoke_sessions: "Завершить все сессии",
  btn_logout_settings: "Выйти из аккаунта",
  confirm_revoke_title: "Завершить все сессии?",
  confirm_revoke_content: "Все устройства будут отключены, потребуется повторный вход.",
  ok_revoke: "Завершить",
  revoke_security_note: "«Завершить все сессии» отзывает все refresh-токены и выходит из системы на всех устройствах.",
  err_wrong_pwd: "Неверный текущий пароль",
  err_rate_limited_pwd: "Слишком много попыток",
  msg_pwd_changed: "Пароль изменён. Выполните вход снова.",
  msg_sessions_revoked: "Все сессии завершены",
  err_revoke_sessions: "Не удалось завершить сессии",
  msg_code_sent: "Код отправлен на ваш email",
  err_send_code: "Не удалось отправить код",
  err_change_pwd: "Ошибка смены пароля",
};

const T: Record<Lang, Translations> = { en, ru };

interface LangCtx {
  lang: Lang;
  L: Translations;
  toggle: () => void;
}

const LangContext = createContext<LangCtx>({
  lang: "en",
  L: en,
  toggle: () => {},
});

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLang] = useState<Lang>(savedLang);

  function toggle() {
    setLang((prev) => {
      const next: Lang = prev === "en" ? "ru" : "en";
      try { localStorage.setItem(STORAGE_KEY, next); } catch {}
      return next;
    });
  }

  return (
    <LangContext.Provider value={{ lang, L: T[lang], toggle }}>
      {children}
    </LangContext.Provider>
  );
}

export function useLang(): LangCtx {
  return useContext(LangContext);
}
