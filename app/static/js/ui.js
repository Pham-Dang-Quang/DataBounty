const translations = {
  en: {
    settings: "Settings", create_call: "Create call", sign_out: "Sign out", sign_in: "Sign in",
    sign_up: "Sign up", footer: "Avalanche Fuji · AI recommendations require caller review",
    account: "Account", name: "Name", email: "Email", password: "Password",
    have_account: "Already have an account?", need_account: "Create an account", profile: "Profile",
    bio: "Bio", profile_picture: "Profile picture", new_password: "New password (optional)", save: "Save",
    wallet: "Fuji wallet", no_wallet: "No wallet linked.", link_wallet: "Link or replace wallet",
    wallet_help: "One wallet can be linked to each account. Linking requires a signature but no transaction.",
    discussion: "Discussion", comment: "Comment", reply: "Reply", post_comment: "Post comment",
    author_links: "Author links", create_data_call: "Create a data call", your_calls: "Your calls",
    open_calls: "Open calls", no_calls: "No funded calls are open yet.",
    hero_eyebrow: "AI-assisted data bounties",
    hero_title: "Request useful data. Review it clearly. Reward it on Avalanche.",
    hero_text: "Create a small data call, fund it on Fuji, and use transparent AI recommendations without giving AI control of funds.",
    describe_dataset: "Describe the smallest useful dataset", title: "Title", data_type: "Data type",
    image: "Image", text: "Text", image_text: "Image-Text pairs", description: "Description", criteria: "Acceptance criteria",
    review_mode: "Review mode", ai_assisted: "AI-assisted", manual: "Manual",
    maximum_accepted: "Maximum accepted", standard_reward: "Standard reward",
    high_reward: "High reward (optional)", high_reward_short: "High reward", deadline: "Deadline (UTC)",
    links_help: "Optional. One link per line, up to five. Use Label | https://example.com.", cancel: "Cancel",
    by: "By", requirements: "Requirements", caller_controls: "Caller controls",
    link_before_funding: "Link a Fuji wallet in account settings before funding.", submit_one: "Submit one",
    to_contribute: "to contribute.", activity: "Activity", to_comment: "to comment.",
    no_comments: "No comments yet.",
    legacy_help: "Existing wallet-only account from an earlier version?",
    legacy_wallet: "Recover with wallet signature", for_call: "For", submitted_data: "Submitted data",
    download_text: "Download text file", ai_recommendation: "AI recommendation",
    manual_review_call: "This call uses manual review.", reward_tier: "Reward tier",
    standard: "Standard", high: "High", accept: "Accept", reject: "Reject",
    caller_review: "Caller review", from: "From", no_contributions: "No contributions yet.",
    error: "Error", action_failed: "That action could not be completed", return_home: "Return home", close: "Close",
    companion_text: "Text label or description", undecided: "Undecided", accepted: "Accepted",
    rejected: "Rejected", no_contributions_in_tab: "No contributions in this tab.", download_csv: "Download CSV file"
  },
  vi: {
    settings: "Cài đặt", create_call: "Tạo yêu cầu", sign_out: "Đăng xuất", sign_in: "Đăng nhập",
    sign_up: "Đăng ký", footer: "Avalanche Fuji · AI chỉ đưa ra đề xuất",
    account: "Tài khoản", name: "Tên", email: "Email", password: "Mật khẩu",
    have_account: "Đã có tài khoản?", need_account: "Tạo tài khoản", profile: "Hồ sơ",
    bio: "Giới thiệu", profile_picture: "Ảnh đại diện", new_password: "Mật khẩu mới (không bắt buộc)", save: "Lưu",
    wallet: "Ví Fuji", no_wallet: "Chưa liên kết ví.", link_wallet: "Liên kết hoặc thay ví",
    wallet_help: "Mỗi tài khoản liên kết một ví. Việc liên kết chỉ cần chữ ký, không tạo giao dịch.",
    discussion: "Thảo luận", comment: "Bình luận", reply: "Trả lời", post_comment: "Gửi bình luận",
    author_links: "Liên kết của tác giả", create_data_call: "Tạo yêu cầu dữ liệu", your_calls: "Yêu cầu của bạn",
    open_calls: "Yêu cầu đang mở", no_calls: "Chưa có yêu cầu nào đã được cấp vốn.",
    hero_eyebrow: "Yêu cầu dữ liệu có AI hỗ trợ",
    hero_title: "Yêu cầu dữ liệu hữu ích. Đánh giá rõ ràng. Trao thưởng trên Avalanche.",
    hero_text: "Tạo một yêu cầu dữ liệu nhỏ, cấp vốn trên Fuji và dùng đề xuất AI minh bạch mà không trao quyền kiểm soát tiền cho AI.",
    describe_dataset: "Mô tả bộ dữ liệu hữu ích nhỏ nhất", title: "Tiêu đề", data_type: "Loại dữ liệu",
    image: "Hình ảnh", text: "Văn bản", image_text: "Cặp hình ảnh-văn bản", description: "Mô tả", criteria: "Tiêu chí chấp nhận",
    review_mode: "Chế độ đánh giá", ai_assisted: "AI hỗ trợ", manual: "Thủ công",
    maximum_accepted: "Số lượng chấp nhận tối đa", standard_reward: "Phần thưởng tiêu chuẩn",
    high_reward: "Phần thưởng cao (không bắt buộc)", high_reward_short: "Phần thưởng cao", deadline: "Hạn chót (UTC)",
    links_help: "Không bắt buộc. Tối đa năm liên kết, mỗi dòng một liên kết. Dùng Nhãn | https://example.com.", cancel: "Hủy",
    by: "Bởi", requirements: "Yêu cầu", caller_controls: "Điều khiển của người tạo",
    link_before_funding: "Hãy liên kết ví Fuji trong cài đặt tài khoản trước khi cấp vốn.", submit_one: "Gửi một",
    to_contribute: "để đóng góp.", activity: "Hoạt động", to_comment: "để bình luận.",
    no_comments: "Chưa có bình luận.",
    legacy_help: "Bạn có tài khoản chỉ dùng ví từ phiên bản trước?",
    legacy_wallet: "Khôi phục bằng chữ ký ví", for_call: "Cho yêu cầu", submitted_data: "Dữ liệu đã gửi",
    download_text: "Tải tệp văn bản", ai_recommendation: "Đề xuất của AI",
    manual_review_call: "Yêu cầu này được đánh giá thủ công.", reward_tier: "Mức thưởng",
    standard: "Tiêu chuẩn", high: "Cao", accept: "Chấp nhận", reject: "Từ chối",
    caller_review: "Đánh giá của người tạo", from: "Từ", no_contributions: "Chưa có đóng góp.",
    error: "Lỗi", action_failed: "Không thể hoàn thành thao tác", return_home: "Về trang chủ", close: "Đóng",
    companion_text: "Nhãn hoặc mô tả văn bản", undecided: "Chưa quyết định", accepted: "Đã chấp nhận",
    rejected: "Đã từ chối", no_contributions_in_tab: "Không có đóng góp trong mục này.", download_csv: "Tải tệp CSV"
  }
};

function applyLanguage(language) {
  const selected = translations[language] ? language : "en";
  document.documentElement.lang = selected;
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    const text = translations[selected][element.dataset.i18n];
    if (text) element.textContent = text;
  });
  const toggle = document.querySelector("[data-language-toggle]");
  if (toggle) toggle.textContent = selected === "en" ? "VI" : "EN";
  localStorage.setItem("language", selected);
}

function showErrorPopup(message) {
  const popup = document.querySelector("#error-popup");
  const messageElement = document.querySelector("#error-popup-message");
  if (!popup || !messageElement) return;
  messageElement.textContent = message;
  messageElement.scrollTop = 0;
  popup.hidden = false;
  document.querySelector("[data-error-popup-close]")?.focus();
}

window.showErrorPopup = showErrorPopup;

document.querySelector("[data-error-popup-close]")?.addEventListener("click", () => {
  document.querySelector("#error-popup").hidden = true;
});

document.querySelector("[data-theme-toggle]")?.addEventListener("click", () => {
  const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("theme", theme);
});

document.querySelector("[data-language-toggle]")?.addEventListener("click", () => {
  applyLanguage(document.documentElement.lang === "vi" ? "en" : "vi");
});

applyLanguage(localStorage.getItem("language") || "en");
