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
    image: "Image", text: "Text", image_text: "Image-Text pairs", image_segmentation_text: "Image-Segmentation-Text", description: "Description", criteria: "Acceptance criteria",
    ai_evaluation_prompt: "Detailed AI evaluation prompt", csv_requirements: "CSV requirements", csv_fields: "Required fields and types", csv_delimiter: "Delimiter", unique_field: "Unique field (optional)", minimum_records: "Minimum records", maximum_records: "Maximum records", maximum_records_help: "Leave blank for no maximum.", no_limit: "No limit", allow_extra_fields: "Allow extra fields", allow_missing_values: "Allow missing values", segmentation_package: "Segmentation package", required_components: "Required components", contribution_irreversible_warning: "Warning: This action cannot be reversed. A submitted contribution cannot be withdrawn.", segmentation_mask_help: "Use clearly separated color regions. Mild shading and anti-aliasing are allowed; photographs, heavy gradients, and complex noise are rejected. The mask and source may have different resolutions, but must have the same aspect ratio.",
    review_mode: "Review mode", ai_assisted: "AI-assisted", manual: "Manual",
    maximum_accepted: "Maximum accepted", standard_reward: "Standard reward", time_remaining: "remaining", deadline_reached: "Deadline reached",
    high_reward: "High reward (optional)", high_reward_short: "High reward", deadline: "Deadline (UTC)",
    links_help: "Optional. One link per line, up to five. Use Label | https://example.com.", cancel: "Cancel",
    by: "By", requirements: "Requirements", caller_controls: "Caller controls",
    link_before_funding: "Link a Fuji wallet in account settings before funding.", submit_one: "Submit one",
    to_contribute: "to contribute.", activity: "Activity", no_activity: "No activity yet.", to_comment: "to comment.",
    no_comments: "No comments yet.",
    legacy_help: "Existing wallet-only account from an earlier version?",
    legacy_wallet: "Recover with wallet signature", for_call: "For", submitted_data: "Submitted data",
    download_text: "Download text file", ai_recommendation: "AI recommendation",
    manual_review_call: "This call uses manual review.", reward_tier: "Reward tier",
    standard: "Standard", high: "High", accept: "Accept", reject: "Reject",
    caller_review: "Caller review", from: "From", no_contributions: "No contributions yet.",
    error: "Error", action_failed: "That action could not be completed", return_home: "Return home", close: "Close",
    companion_text: "Text label or description", undecided: "Undecided", accepted: "Accepted",
    rejected: "Rejected", no_contributions_in_tab: "No contributions in this tab.", download_csv: "Download CSV file", view_csv: "Open CSV for review",
    moderators: "Moderators", moderator_email: "Moderator account email", add_moderator: "Add moderator",
    remove: "Remove", no_moderators: "No moderators assigned.", moderator_controls: "Moderator controls",
    moderator_scope: "You may review data, but cannot edit, remove, fund, or pay this call.",
    apply_ai: "Apply AI recommendations", download_accepted: "Download accepted ZIP",
    decided_by: "Decided by", reaccept: "Re-accept", approve_for_payout: "Approve for payout",
    payout_confirmation_pending: "Payout submitted. Waiting for Fuji confirmation.",
    protected_preview_notice: "Protected low-resolution image preview. Repeated watermarks are baked into the stored derivative.",
    additional_contributions: "Additional contribution acceptances", top_up_help: "Each added slot funds the call's maximum reward tier.", fund_more: "Fund more DBT",
    filter_ai: "Filter AI recommendations", ai_accept: "AI accept", ai_reject: "AI reject", ai_unsure: "AI unsure", apply_filter: "Apply filter", clear_filter: "Clear",
    acceptance_funding_required: "The funded acceptance limit is full. New contributions remain reviewable, but the caller must fund more DBT before accepting another."
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
    image: "Hình ảnh", text: "Văn bản", image_text: "Cặp hình ảnh-văn bản", image_segmentation_text: "Hình ảnh-Phân đoạn-Văn bản", description: "Mô tả", criteria: "Tiêu chí chấp nhận",
    ai_evaluation_prompt: "Yêu cầu đánh giá AI chi tiết", csv_requirements: "Yêu cầu CSV", csv_fields: "Trường và kiểu dữ liệu bắt buộc", csv_delimiter: "Dấu phân cách", unique_field: "Trường duy nhất (không bắt buộc)", minimum_records: "Số bản ghi tối thiểu", maximum_records: "Số bản ghi tối đa", maximum_records_help: "Để trống nếu không giới hạn.", no_limit: "Không giới hạn", allow_extra_fields: "Cho phép trường bổ sung", allow_missing_values: "Cho phép giá trị trống", segmentation_package: "Gói phân đoạn", required_components: "Thành phần bắt buộc", contribution_irreversible_warning: "Cảnh báo: Hành động này không thể hoàn tác. Dữ liệu đã đóng góp không thể rút lại.", segmentation_mask_help: "Dùng các vùng màu tách biệt rõ. Cho phép đổ bóng nhẹ và làm mịn cạnh; ảnh chụp, chuyển sắc mạnh và nhiễu phức tạp sẽ bị từ chối. Mặt nạ và ảnh gốc có thể khác độ phân giải, nhưng phải có cùng tỷ lệ khung hình.",
    review_mode: "Chế độ đánh giá", ai_assisted: "AI hỗ trợ", manual: "Thủ công",
    maximum_accepted: "Số lượng chấp nhận tối đa", standard_reward: "Phần thưởng tiêu chuẩn", time_remaining: "còn lại", deadline_reached: "Đã hết hạn",
    high_reward: "Phần thưởng cao (không bắt buộc)", high_reward_short: "Phần thưởng cao", deadline: "Hạn chót (UTC)",
    links_help: "Không bắt buộc. Tối đa năm liên kết, mỗi dòng một liên kết. Dùng Nhãn | https://example.com.", cancel: "Hủy",
    by: "Bởi", requirements: "Yêu cầu", caller_controls: "Điều khiển của người tạo",
    link_before_funding: "Hãy liên kết ví Fuji trong cài đặt tài khoản trước khi cấp vốn.", submit_one: "Gửi một",
    to_contribute: "để đóng góp.", activity: "Hoạt động", no_activity: "Chưa có hoạt động.", to_comment: "để bình luận.",
    no_comments: "Chưa có bình luận.",
    legacy_help: "Bạn có tài khoản chỉ dùng ví từ phiên bản trước?",
    legacy_wallet: "Khôi phục bằng chữ ký ví", for_call: "Cho yêu cầu", submitted_data: "Dữ liệu đã gửi",
    download_text: "Tải tệp văn bản", ai_recommendation: "Đề xuất của AI",
    manual_review_call: "Yêu cầu này được đánh giá thủ công.", reward_tier: "Mức thưởng",
    standard: "Tiêu chuẩn", high: "Cao", accept: "Chấp nhận", reject: "Từ chối",
    caller_review: "Đánh giá của người tạo", from: "Từ", no_contributions: "Chưa có đóng góp.",
    error: "Lỗi", action_failed: "Không thể hoàn thành thao tác", return_home: "Về trang chủ", close: "Đóng",
    companion_text: "Nhãn hoặc mô tả văn bản", undecided: "Chưa quyết định", accepted: "Đã chấp nhận",
    rejected: "Đã từ chối", no_contributions_in_tab: "Không có đóng góp trong mục này.", download_csv: "Tải tệp CSV", view_csv: "Mở CSV để đánh giá",
    moderators: "Người kiểm duyệt", moderator_email: "Email tài khoản kiểm duyệt", add_moderator: "Thêm người kiểm duyệt",
    remove: "Xóa", no_moderators: "Chưa chỉ định người kiểm duyệt.", moderator_controls: "Điều khiển kiểm duyệt",
    moderator_scope: "Bạn có thể đánh giá dữ liệu nhưng không thể sửa, xóa, cấp vốn hoặc thanh toán yêu cầu này.",
    apply_ai: "Áp dụng đề xuất AI", download_accepted: "Tải ZIP dữ liệu đã chấp nhận",
    decided_by: "Quyết định bởi", reaccept: "Chấp nhận lại", approve_for_payout: "Duyệt để thanh toán",
    payout_confirmation_pending: "Đã gửi thanh toán. Đang chờ Fuji xác nhận.",
    protected_preview_notice: "Bản xem trước hình ảnh độ phân giải thấp. Hình mờ lặp lại đã được ghi vào bản sao được lưu trữ.",
    additional_contributions: "Số đóng góp có thể chấp nhận thêm", top_up_help: "Mỗi suất bổ sung cấp vốn theo mức thưởng tối đa của yêu cầu.", fund_more: "Cấp thêm DBT",
    filter_ai: "Lọc đề xuất AI", ai_accept: "AI chấp nhận", ai_reject: "AI từ chối", ai_unsure: "AI chưa chắc chắn", apply_filter: "Áp dụng bộ lọc", clear_filter: "Xóa bộ lọc",
    acceptance_funding_required: "Đã dùng hết giới hạn chấp nhận được cấp vốn. Vẫn có thể xem đóng góp mới, nhưng người tạo phải cấp thêm DBT trước khi chấp nhận."
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

if (document.querySelector("[data-payout-pending]")) {
  window.setTimeout(() => window.location.reload(), 5000);
}

if (!document.querySelector("#error-popup")?.hidden) {
  document.querySelector("[data-error-popup-close]")?.focus();
}

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

document.querySelectorAll("[data-protected-preview]").forEach((preview) => {
  ["contextmenu", "copy", "cut", "dragstart"].forEach((eventName) => {
    preview.addEventListener(eventName, (event) => event.preventDefault());
  });
});

function updateCallTypeFields() {
  const selector = document.querySelector("[data-call-type-select]");
  if (!selector) return;
  document.querySelectorAll("[data-call-type-fields]").forEach((group) => {
    const active = group.dataset.callTypeFields === selector.value;
    group.hidden = !active;
    group.querySelectorAll("input, select, textarea").forEach((control) => {
      control.disabled = !active;
    });
  });
  const reviewMode = document.querySelector("[data-review-mode]");
  const requiresAi = selector.value === "csv" || selector.value === "image_segmentation_text";
  if (reviewMode) {
    reviewMode.querySelector('option[value="manual"]').disabled = requiresAi;
    if (requiresAi) reviewMode.value = "ai_assisted";
  }
}

document.querySelector("[data-call-type-select]")?.addEventListener("change", updateCallTypeFields);

function updateDeadlineCountdowns() {
  const language = translations[document.documentElement.lang] ? document.documentElement.lang : "en";
  const words = translations[language];
  const now = Math.floor(Date.now() / 1000);
  document.querySelectorAll("[data-deadline-countdown]").forEach((element) => {
    const deadline = Number(element.dataset.deadlineCountdown);
    const remaining = Math.max(0, deadline - now);
    if (!Number.isFinite(deadline) || remaining === 0) {
      element.textContent = words.deadline_reached;
      return;
    }
    const days = Math.floor(remaining / 86400);
    const hours = Math.floor((remaining % 86400) / 3600);
    const minutes = Math.floor((remaining % 3600) / 60);
    const seconds = remaining % 60;
    element.textContent = `${days}d ${String(hours).padStart(2, "0")}h ${String(minutes).padStart(2, "0")}m ${String(seconds).padStart(2, "0")}s ${words.time_remaining}`;
  });
}

applyLanguage(localStorage.getItem("language") || "en");
updateCallTypeFields();
updateDeadlineCountdowns();
window.setInterval(updateDeadlineCountdowns, 1000);
