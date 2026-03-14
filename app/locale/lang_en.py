from app.settings import secrets

news_url = secrets.get('news_url')

text_help = """
<b>📱 VPN Setup via Happ</b>

<u>🔹 STEP 1: Install the app</u>
Download <b>Happ</b> for:
• iOS: <a href="https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973">download</a>
• Android: <a href="https://play.google.com/store/apps/details?id=com.happproxy">download</a>

<u>🔹 STEP 2: Get a subscription</u>
1️⃣ Purchase a VPN subscription
2️⃣ Copy the 🔑 <b>connection link</b> from the received message

<u>🔹 STEP 3: Import the key</u>
1. Open the app
2. Tap ➕ <b>in the top right corner</b>
3. Select 📋 <b>"Import from clipboard"</b>

<u>🔹 STEP 4: Connect</u>
1. Go to 🌐 <b>"Cheezy VPN"</b> section
2. Select a server from the list
3. Tap 🔛 <b>the connect button</b>

<code>💡 Important:</code>
• Make sure the link is copied before importing
• Allow VPN connection on first launch
• To switch servers: ⏹️ stop → select new → ▶️
"""

text_help_windows = """
<b>📱 VPN Setup via Throne</b>

<u>🔹 STEP 1: Install the client</u>
Download <b><a href="https://github.com/throneproj/Throne/releases">Throne</a></b>

<u>🔹 STEP 2: Get a subscription</u>
1️⃣ Purchase a VPN subscription
2️⃣ Copy the 🔑 <b>connection link</b> from the received message

<u>🔹 STEP 3: Import the key</u>
1. Open Throne
2. Click Application <b>in the top left corner</b>
3. Select <b>"Add profile from clipboard"</b>
4. Choose <b>"Create new subscription group"</b> and click <b>"OK"</b>

<u>🔹 STEP 4: Connect</u>
1. In the new subscription group select the desired server (right-click -> start)
2. Check the <b>"Tun Mode"</b> checkbox

<code>💡 Important:</code>
• Make sure the link is copied before importing
• Allow network access for the client in the firewall popup on first launch
• To switch servers: right-click → start on another server from the list
• To disconnect VPN: uncheck Tun Mode
"""

text_pay_method = ("<b>Choose a convenient payment method:</b>\n\n"
                   "Pick the option that works for you — payment is secure\n")

text_extend_pay_method = "<b>Subscription renewal — choose a payment method:</b>\n"

instrustion_platform_choose = """
After successful payment you will receive a personal <b>connection link</b> to the VPN server.

<b>📱 How to use:</b>
1. Copy the received subscription link
2. Install one of the recommended clients:

<b>For Windows:</b>
• v2rayN
• Throne
• Invisible Man - Xray

<b>For Android/iOS:</b>
• Happ
• V2RayTun
• Hidify

Full list of compatible apps is available on
<a href="https://github.com/XTLS/Xray-core?tab=readme-ov-file#gui-clients">GitHub</a>

3. Add the subscription link to the chosen app
4. Connect to the VPN server

More detailed setup instructions are below 👇
"""

text_answers = {
    'main_menu_greetings': "You are in the main menu",
    'instruction_greetings': "Instructions section",
    'instruction_platform_choose': instrustion_platform_choose,
    'instruction_android': "Instructions for Android",
    'instruction_windows': "Instructions for Windows/Linux"
}

start_base = ("<b>Welcome to CheezyVPN!</b>\n\n"
              "Internet without borders — just as it was meant to be:\n\n"
              "🌍 <b>Access your favorite services</b> — streaming, AI tools, "
              "international platforms work without restrictions\n"
              "🎮 <b>Comfortable gaming</b> — stable connection "
              "and optimal ping for online games\n"
              "🔒 <b>Privacy</b> — modern encryption, "
              "no logs and full anonymity\n"
              "📱 <b>Easy setup</b> — connect in a few clicks "
              "on any device\n\n"
              "Netflix, Spotify, ChatGPT, Midjourney and more — "
              "everything is available with CheezyVPN\n")
start_new = "<b>Try for free or choose PRO — it's up to you</b>\n\n"
start_free = ("📱 <b>Your FREE subscription is active</b>\n\n"
              "Want more?\n"
              "With <b>PRO</b> plan you get:\n"
              "• Unlimited traffic — streams, AI tools and games without limits\n"
              "• Up to 5 devices simultaneously\n"
              "• Stable connection for everything you need\n\n"
              "Try PRO — the difference is noticeable right away\n\n")
start_pro = ("⚡️ <b>You're with us — great!</b>\n"
             "Below — information about your current subscription and the option to renew it\n\n")

free_menu = (f"<b>Almost there!</b>\n\n"
             f"Subscribe to our channel <a href='{news_url}'>Cheezy VPN</a> "
             f"to get free access\n\n"
             "Already subscribed? Tap the button below\n")

free_menu_notsub = (f"<b>You haven't subscribed to the channel yet</b> "
                    f"<a href='{news_url}'>Cheezy VPN</a>\n\n"
                    "Subscribe — and free access is yours\n")

start_agreement = (
    "<b>By using CheezyVPN, you agree to the Terms of Service "
    "and Privacy Policy. Please review the documents before payment</b>\n")

user_agreement = (f"""
<b>🔒 CheezyVPN TERMS OF SERVICE</b>

<b>1. Subject of agreement</b>
1.1. The service provides VPN access via Telegram bot
1.2. Services are available only to adults
1.3. Using the bot = acceptance of the offer

<b>2. User obligations</b>
- Do not violate applicable laws
- Do not distribute malware
- Do not use for DDoS/spam/hacking
- <u>Account transfer to third parties is prohibited</u>

<b>3. Payment and refund</b>
3.1. Payment via bot (cards/Telegram Stars/Crypto)
3.2. Refund only if technically unable to provide the service

<b>4. Liability</b>
4.1. <i>We do not guarantee 100% VPN availability</i>
4.2. <i>We are not responsible for:</i>
    • Illegal actions of users
    • Damage due to VPN outages
    • Access blocks to resources

<b>5. Termination</b>
5.1. Account blocking for violations without refund
5.2. Service cancellation = stopping payment

<b>6. Contacts</b>
Support: {secrets.get('support_bot_id')}


<em>By using the service, you confirm your agreement with the terms</em>
""")
privacy_policy = f"""
<b>🔐 CheezyVPN PRIVACY POLICY</b>

<b>1. Collected data</b>
1.1. <u>Required:</u>
- Telegram User ID
- Telegram username
- Payment data
1.2. <u>Technical:</u>
- Connection time
- Device type
- Traffic volume

<b>2. Collection prohibition</b>
🚫 We never store:
- Browsing history
- User IP addresses
- Transmitted content

<b>3. Data usage</b>
Only for:
- Activating VPN access
- Technical support
- Tariff notifications

<b>4. Data protection</b>
4.1. Storage on encrypted servers
4.2. Keys are deleted when subscription is cancelled

<b>5. Data transfer</b>
Only to:
- Payment systems
- As required by law

<b>6. Retention period</b>
Deleted within 30 days after:
- Subscription cancellation
- Your request

<b>7. Your rights</b>
You can request:
→ Access to data
→ Information correction
→ Account deletion

Contacts: {secrets.get('support_bot_id')}
"""

# Messages and status
subscription_messages = {
    'payment_success_thanks': "Thank you for your purchase!",
    'payment_success_new': "<b>PRO subscription activated</b>",
    'payment_success_extended': "<b>Subscription extended</b>",
    'payment_success_updated': "<b>Subscription updated</b>",
    'free_success_new': "<b>FREE subscription activated</b>",
    'free_success_updated': "<b>Subscription updated</b>",
    'free_already_active': "<b>FREE subscription is already active</b>",
    'subscription_link': "Connection link:",
    'days_remaining': "Days remaining: {days}",
    'days_will_last': "Valid for: {days} days",
    'user_not_found': "User not found — creating new according to tariff",
    'user_found_updating': "User found — updating data",
}

# Formatted subscription response templates
subscription_response_templates = {
    'new_paid': """Thank you for your purchase!

<b>PRO subscription activated</b>
Valid for: {days} days

Connection link:
<code>{link}</code>""",

    'extended_paid': """Thank you for your purchase!

<b>Subscription extended</b>
Days remaining: {days}

Connection link:
<code>{link}</code>""",

    'updated_paid': """Thank you for your purchase!

<b>Subscription updated</b>
Days remaining: {days}

Connection link:
<code>{link}</code>""",

    'new_free': """<b>FREE subscription activated</b>
Valid for: {days} days

Connection link:
<code>{link}</code>""",

    'updated_free': """<b>Subscription updated</b>
Days remaining: {days}

Connection link:
<code>{link}</code>""",

    'already_active_free': """<b>FREE subscription is already active</b>
Days remaining: {days}

Connection link:
<code>{link}</code>""",
}

# Admin transaction message (kept in Russian as admin messages are excluded)
admin_transaction_message = """Транзакция ID - {payment_method}
Пользователь - @{username}
UserId - {user_id}
Количество дней - {days}"""

# Marzban migration messages
marzban_user_with_upgrade_option = """<b>We've updated our infrastructure!</b>

New servers — more stable and reliable:

• Improved security
• Optimized traffic
• Reliable connection

<b>All parameters will be preserved:</b>
✓ Remaining subscription days
✓ Traffic limit
✓ Access settings

The transition is free — choose «Migrate to Beta» below
"""

migration_success = """<b>Migration complete!</b>

Your subscription has been transferred to new servers.

<b>Connection link:</b>
<code>{link}</code>

<b>Parameters:</b>
• Days remaining: {days}
• Traffic limit: {limit} GB

<b>What's next:</b>
1. Copy the new link
2. Add it to your VPN app
3. Connect

The old link no longer works.
"""

migration_error = """<b>Migration failed</b>

Possible reasons:
• Server connection issue
• Insufficient user data

Contact support — we'll help: @{support_bot}

Your current subscription remains active.
"""

migration_in_progress = """<b>Transferring subscription to new server...</b>

This will take a few seconds
"""

# Admin migration message (kept in Russian)
admin_migration_message = """✅ <b>Миграция пользователя успешна</b>

👤 Пользователь: @{username}
🆔 User ID: {user_id}
⏱️ Дней подписки: {expire_days}
💾 Лимит трафика: {data_limit} GB
🏷️ Тип: {sub_type}"""

# ==================== Promo / Referral ====================

promo_invite_text = """<b>Invite friends — get bonuses</b>

Your promo code: <code>{promo_code}</code>

<b>How it works:</b>
1. Share your promo code with friends
2. A friend gets a <b>{discount}%</b> discount on purchase
3. For every 30 days purchased with your code, you receive <b>{reward_days}</b> bonus days

<b>Your stats:</b>
• Purchased via promo code: {days_purchased} days
• Bonus days received: {days_rewarded}"""

promo_enter_text = "Enter promo code:"

promo_success_text = "Promo code applied! <b>{discount}%</b> discount will be applied at payment."

promo_invalid_text = "Invalid promo code — please check and try again."

promo_own_code_text = "You cannot use your own promo code."

promo_already_used_text = "You have already used a promo code."

free_traffic_exhausted = """<b>FREE subscription traffic exhausted</b>

Renewal in <b>{days}</b> days.

Switch to <b>PRO</b> — unlimited traffic and up to 5 devices without waiting"""

promo_reward_notification = """<b>Referral bonus!</b>

A purchase was made with your promo code — you've been credited <b>{reward_days}</b> subscription days.

Total purchased via promo code: {total_days} days
Total bonus days: {total_rewarded}"""

# ==================== Language Selection ====================

lang_choose = "🌐 <b>Выберите язык / Choose language:</b>"
lang_btn_ru = "🇷🇺 Русский"
lang_btn_en = "🇬🇧 English"

# ==================== Settings ====================

btn_settings = "⚙️ Settings"
btn_language = "🌐 Language"
msg_settings = "<b>⚙️ Settings</b>\n\nHere you can change the language and review documents."
msg_lang_current = "🌐 Current language: <b>English</b>\n\nChoose language:"

# ==================== Button Labels ====================

btn_buy_premium = "🔒Buy CheezeVPN Premium⭐️"
btn_extend_subscription = "🔒Extend subscription"
btn_install_instructions = "Setup instructions"
btn_free_version = "Free version"
btn_invite_friends = "👥 Invite friends"
btn_user_agreement = "Terms of Service"
btn_privacy_policy = "Privacy Policy"
btn_sub_info = "Subscription info"
btn_to_main = "Main menu"
btn_back = "◀️ Back"
btn_open = "Open"
btn_i_subscribed = "I've subscribed!"
btn_full_text = "Full text"
btn_buy_subscription = "Buy subscription"
btn_migrate_beta = "🚀 Migrate to Beta"
btn_confirm_migration = "✅ Confirm migration"
btn_cancel = "❌ Cancel"
btn_buy_premium_short = "🔒Buy Premium⭐️"

# Payment buttons
btn_pay_stars = "⭐ Telegram Stars"
btn_pay_crypto = "💰 CryptoBot"
btn_pay_crystal = "🔷 Crystal Pay"
btn_pay_card = "💳 Bank card"
btn_pay_amount = "Pay {amount} ⭐️"
btn_have_promo = "🎁 I have a promo code"

# Platform buttons
btn_platform_android = "Android/IOS - Happ"
btn_platform_windows = "Windows/Linux - Throne"

# Tariff labels
tariff_unlimited = "🔒UNLIMITED"

# ==================== Misc Messages ====================

msg_account_banned = "Your account is blocked."
msg_buying_premium = "Buying Premium subscription"
msg_extending_premium = "Extending Premium subscription"
msg_choose_tariff = "Choose a tariff plan"
msg_pay_in_stars = "Paying subscription in ⭐"
msg_invoice_title = "Monthly subscription payment"
msg_invoice_description = "Purchase for {amount} ⭐️!"
msg_order_paid = "Order #{invoice_id} successfully paid"
msg_pay_link = "Payment link: {link}"
msg_already_on_beta = "❌ <b>You are already registered on Beta!</b>"

# Subscription info
msg_pro_active = "Pro subscription active\nConnection link: {link}\nDays remaining: {days}\n"
msg_free_active = "Free subscription active\nConnection link: {link}\nDays remaining: {days}\n"

# Subscription info block for main menu greeting
sub_info_block = ("📊 <b>Your subscription:</b>\n"
                  "🏷️ Plan: <b>{plan}</b>\n"
                  "⏳ Days remaining: <b>{days}</b>\n"
                  "📶 Traffic limit: <b>{traffic}</b>\n")

# Tariff periods
period_1month = "1 Month"
period_3months = "3 Months"
period_1year = "Year"
