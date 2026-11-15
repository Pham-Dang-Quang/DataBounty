# Minimal Database

Status: SQLite MVP

## `users`

- `id`
- `wallet_address` (unique)
- `created_at`

## `auth_nonces`

- `id`, `wallet_address`, `nonce_hash`
- `expires_at`, `used_at`

## `data_calls`

- `id`, `caller_id`
- `title`, `description`, `data_type`
- `acceptance_criteria`, `review_mode`
- `standard_reward`, `high_reward`
- `max_acceptances`, `deadline`
- `status`, `escrow_call_id`, `funding_tx_hash`
- `created_at`

## `contributions`

- `id`, `call_id`, `contributor_id`
- `stored_filename`, `original_filename`, `sha256`, `media_type`, `size_bytes`
- `status`
- `ai_recommendation`, `ai_tier`, `ai_explanation`, `model_name`
- `final_decision`, `final_tier`, `reward_amount`
- `payout_tx_hash`
- `created_at`, `reviewed_at`

## `events`

- `id`, `call_id`, optional `contribution_id`
- `event_type`, `message`, optional `tx_hash`
- `created_at`

## Constraints

- Store token amounts as integers in minor units.
- A contribution hash is unique within a call.
- A contribution has at most one payout transaction.
- Only the caller may finalize a decision.
- Open calls must have confirmed funding.
- Uploaded files use generated names and are not publicly served.

Avoid additional tables until a demonstrated feature requires them.
