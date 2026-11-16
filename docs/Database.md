# Minimal Database

Status: SQLite MVP

## `users`

- `id`
- `email` (unique), `password_hash`
- `display_name`, `bio`, `profile_image`
- `wallet_address` (unique; temporary local identifier until a wallet is linked)
- `created_at`

## `auth_nonces`

- `id`, `wallet_address`, `nonce_hash`
- `expires_at`, `used_at`

## `data_calls`

- `id`, `caller_id`
- `title`, `description`, `data_type` (`image_text` or `csv`)
- `acceptance_criteria`, `review_mode`
- `standard_reward`, `high_reward`
- `max_acceptances`, `deadline`
- `status`, `escrow_call_id`, `funding_tx_hash`
- `created_at`

## `contributions`

- `id`, `call_id`, `contributor_id`
- `stored_filename`, `original_filename`, `sha256`, `media_type`, `size_bytes`
- optional `companion_text` (required by application validation for image-text pairs)
- `status`
- `evaluation_progress`, `evaluation_stage`
- `ai_recommendation`, `ai_tier`, `ai_explanation`, `model_name`
- `final_decision`, `final_tier`, `reward_amount`
- `payout_tx_hash`
- `created_at`, `reviewed_at`

## `events`

- `id`, `call_id`, optional `contribution_id`
- `event_type`, `message`, optional `tx_hash`
- `created_at`

## `call_links`

- `id`, `call_id`
- `label`, `url`

## `comments`

- `id`, `call_id`, `author_id`
- optional `parent_id` for one-level replies
- `body`, `created_at`

## Constraints

- Store token amounts as integers in minor units.
- A contribution hash is unique within a call.
- A contribution has at most one payout transaction.
- Only the caller may finalize a decision.
- Open calls must have confirmed funding.
- `escrow_call_id` is a random positive 63-bit value and is independent of the resettable SQLite ID.
- Only an unfunded draft may be updated or deleted; deletion also removes its draft-only events.
- Uploaded files use generated names and are not publicly served.
- A call accepts at most five HTTP(S) links through application validation.
- Replies may target only a top-level comment.

Avoid additional tables until a demonstrated feature requires them.
