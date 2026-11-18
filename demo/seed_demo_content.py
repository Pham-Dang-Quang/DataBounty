# ruff: noqa: E501
"""Seed reproducible synthetic demo accounts, calls, and discussions.

Generated account and fixture outputs are local-only. The script is idempotent by email/title.
"""

from __future__ import annotations

import csv
import hashlib
import shutil
import sys
from datetime import timedelta
from pathlib import Path

from PIL import Image, ImageDraw
from sqlalchemy import delete, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.auth import hash_password  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import Database  # noqa: E402
from app.models import (  # noqa: E402
    CallLink,
    CallStatus,
    Comment,
    Contribution,
    ContributionStatus,
    DataCall,
    User,
    utcnow,
)

PASSWORD = "DemoPass!2026"
ACCOUNT_DIR = ROOT / "demo_account"
DATA_DIR = ROOT / "demo_data"
GENERATE_FIXTURES = False
DEMO_IDENTITIES = [
    ("alice.nguyen@databounty.local", "Alice Nguyen"),
    ("bao.tran@databounty.local", "Bao Tran"),
    ("chi.le@databounty.local", "Chi Le"),
    ("duy.pham@databounty.local", "Duy Pham"),
    ("emily.carter@databounty.local", "Emily Carter"),
    ("frank.miller@databounty.local", "Frank Miller"),
    ("grace.kim@databounty.local", "Grace Kim"),
    ("huy.vo@databounty.local", "Huy Vo"),
    ("isabel.martin@databounty.local", "Isabel Martin"),
    ("jonathan.reed@databounty.local", "Jonathan Reed"),
]


def wallet_for(index: int) -> str:
    return "0x" + hashlib.sha256(f"databounty-demo-wallet-{index}".encode()).hexdigest()[:40]


def write_image(path: Path, label: str, accent: tuple[int, int, int], quality: str) -> None:
    image = Image.new("RGB", (640, 400), (238, 242, 246))
    draw = ImageDraw.Draw(image)
    draw.rectangle((32, 32, 608, 368), outline=accent, width=8)
    draw.ellipse((180, 90, 460, 370), fill=accent, outline=(30, 30, 30), width=4)
    draw.text((52, 52), f"{label} | {quality}", fill=(20, 20, 20))
    if quality == "good":
        draw.line((250, 210, 390, 210), fill=(255, 255, 255), width=8)
        draw.line((320, 140, 320, 280), fill=(255, 255, 255), width=8)
    elif quality == "low":
        draw.rectangle((0, 0, 640, 400), fill=(150, 150, 150, 80))
    marker = int(hashlib.sha256(label.encode()).hexdigest()[:6], 16)
    draw.rectangle((48, 330, 48 + marker % 80, 350), fill=(marker % 255, (marker // 3) % 255, (marker // 7) % 255))
    image.save(path, format="PNG")


def write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def discussion_prompts(title: str) -> list[str]:
    if "Chest X-Ray" in title:
        return [
            "Should the mask include the costophrenic angles when they are partly outside the frame?",
            "I would require the image and mask to have identical dimensions before discussing clinical quality.",
            "How do we handle portable AP films with rotation or under-exposure?",
            "A small amount of border noise seems acceptable if the lung boundary remains traceable.",
            "Please do not infer a diagnosis from the image; review only the segmentation quality.",
            "Would a separate flag for clipped lungs be more useful than rejecting the entire sample?",
            "For ambiguous boundaries, should the annotation follow the visible pleura or the expected anatomy?",
            "I support a conservative mask: uncertain pixels should stay background rather than become lung.",
            "The AI explanation should call out missing lungs and empty masks explicitly.",
            "Can we document whether tubes and other devices are included in the mask?",
            "A reviewer needs the original acquisition view and not a contrast-enhanced preview.",
            "I found that consistent naming of left and right lungs makes adjudication much faster.",
            "Low-quality does not always mean invalid; a technically valid rotated film can remain reviewable.",
            "Let us reserve rejection for dimension, file, or anatomy failures and use low tier for noisy edges.",
            "The acceptance threshold should be applied consistently across portable and standard films.",
        ]
    if "NOAA" in title:
        return [
            "Should timestamps be normalized to UTC before the reviewer sees the table?",
            "I would reject a blank station ID even if the other measurements look plausible.",
            "A second row is useful, but it should not be copied from the first row with a changed timestamp.",
            "Please distinguish a calm sea from a sensor that reported zero because it failed.",
            "Would a station metadata link help reviewers validate the station ID?",
            "The low tier should cover sparse but parseable data, not malformed CSV.",
            "Air temperature and wave height need units in the header or call documentation.",
            "I prefer rejecting impossible numeric values before asking the model for a quality score.",
            "Can we flag duplicate observations by station and timestamp?",
            "A short provenance note would make these observations more useful downstream.",
            "The model should explain whether its concern is schema, plausibility, or coverage.",
            "Two valid rows from different stations are acceptable if both station IDs are real.",
            "Please keep missing-value policy explicit; silent imputation would hide a contributor mistake.",
            "A reviewer should not reward precision formatting when the underlying values are implausible.",
            "I support a high tier only when both rows are coherent and the units are unambiguous.",
        ]
    if "Street-sign" in title:
        return [
            "The sign face should be readable without relying on the caption to guess its class.",
            "A wide road context is helpful, but it should not make the sign too small to inspect.",
            "Should partially occluded signs be low quality or rejected as invalid?",
            "I would reject captions that claim a sign type not visible in the image.",
            "Country context matters because the same symbol can have different meanings.",
            "Please avoid accepting images with visible license plates in the background.",
            "Blur and glare should be discussed separately from an actually unrelated photo.",
            "A good sample needs enough perspective to show where the sign is placed on the road.",
            "Could we ask contributors to mention whether the sign is regulatory, warning, or informational?",
            "The AI should not treat a long caption as evidence that the image is correct.",
            "I would rather see a short precise caption than a speculative location story.",
            "A sign partly hidden by foliage may be useful for training but should not receive high tier.",
            "Reviewers should compare the caption and pixels before trusting the recommendation.",
            "If the sign is readable but the road context is absent, standard tier seems fair.",
            "The strongest submissions make the sign class obvious at first glance.",
        ]
    if "Urban tree" in title:
        return [
            "A useful note should separate visible symptoms from guesses about the cause.",
            "Please describe the trunk and canopy even when species identification is uncertain.",
            "A distant tree photo can be valid but should not receive the high tier.",
            "We should reject images dominated by faces or license plates for privacy reasons.",
            "Seasonal leaf loss should not automatically be labeled poor health.",
            "The curb, sidewalk, and planting strip are important parts of the urban setting.",
            "Could contributors mention whether pruning wounds or supports are visible?",
            "The AI should not infer pests from a low-resolution image without visible evidence.",
            "I would use low tier for a clear tree with a vague note, not reject it outright.",
            "A consistent observation vocabulary would make notes easier to compare.",
            "Good photos show enough of the tree to connect the canopy and trunk observations.",
            "Please distinguish a dead branch from a shadow before making a health claim.",
            "The companion text should state uncertainty instead of inventing a species.",
            "One tree per contribution keeps the labels focused and avoids mixed observations.",
            "The strongest samples combine a clear image with restrained, observable language.",
        ]
    if "USGS" in title:
        return [
            "The pH range check should happen before any quality judgment.",
            "Repeated station readings are more useful than many unrelated station IDs.",
            "A timestamp without a timezone is ambiguous and should fail validation.",
            "Please keep discharge and temperature units in the call schema, not only in prose.",
            "A blank value should remain blank rather than being silently converted to zero.",
            "Low quality can mean thin temporal coverage even when the CSV parses correctly.",
            "The model should explain whether a concern is physical plausibility or missing structure.",
            "Would a station metadata URL help us catch accidental station typos?",
            "Two rows should represent observations, not two copies of one record.",
            "A stable pH series is stronger evidence than excessive decimal precision.",
            "Please flag impossible temperatures separately from a missing measurement.",
            "I support rejecting extra columns unless the contributor explains them.",
            "The reviewer should inspect row order and timestamp spacing for obvious duplication.",
            "Good data is both machine-readable and understandable to a hydrology reviewer.",
            "A high tier should require complete rows across all five required fields.",
        ]
    return [
        "The image and mask must have identical dimensions before visual quality is discussed.",
        "Only black, gray, and white should appear in the flat-color mask.",
        "A clean lane boundary matters more than a large painted road region.",
        "Gradients usually indicate an export problem rather than a useful annotation.",
        "Please describe the scene in the companion text without adding unsupported claims.",
        "A valid but noisy mask should be low tier, not automatically rejected.",
        "The mask should leave obvious background outside the drivable road.",
        "Could we document how to handle dashed lane markings and occlusions?",
        "The AI should call out empty masks and all-road masks explicitly.",
        "Matching dimensions are necessary but not sufficient for a good segmentation.",
        "I would check the original image before deciding whether a boundary is truly ambiguous.",
        "A contributor should not use a caption to compensate for a missing mask region.",
        "The strongest samples show lane markings with clean, consistent edges.",
        "Please keep the mask palette deterministic so downstream training does not need recoloring.",
        "A reviewer can accept a difficult scene when the annotation is internally consistent.",
    ]


def add_file(call_dir: Path, name: str, kind: str, label: str, quality: str) -> Path:
    call_dir.mkdir(parents=True, exist_ok=True)
    path = call_dir / name
    sample_number = int(hashlib.sha256(path.stem.encode()).hexdigest()[:8], 16) % 86400
    if kind == "csv":
        if quality == "invalid":
            write_csv(path, ["station_id", "observed_at"], [["", f"not-a-date-{sample_number}"]])
        elif quality == "low":
            write_csv(
                path,
                ["station_id", "observed_at", "air_temp_c", "wave_height_m"],
                [["44013", f"2026-01-02T00:{sample_number % 60:02d}:00Z", "", f"0.{sample_number % 9 + 1}"]],
            )
        else:
            write_csv(
                path,
                ["station_id", "observed_at", "air_temp_c", "wave_height_m"],
                [
                    ["44013", f"2026-01-02T00:{sample_number % 60:02d}:00Z", f"{12 + sample_number % 5}.4", "1.8"],
                    ["46042", f"2026-01-02T01:{sample_number % 60:02d}:00Z", f"{11 + sample_number % 5}.9", "2.1"],
                ],
            )
    else:
        write_image(path, f"{label} {path.stem}", (35, 105, 180) if quality == "good" else (170, 80, 45), quality)
    return path


def seed() -> None:
    settings = get_settings()
    settings.ensure_directories()
    db = Database(settings.database_url)
    db.create_tables()
    ACCOUNT_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)
    with db.session_factory() as session:
        users: list[User] = []
        for index in range(1, 11):
            email, display_name = DEMO_IDENTITIES[index - 1]
            old_email = f"demo{index:02d}@databounty.local"
            user = session.scalar(select(User).where(User.email == old_email)) or session.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    wallet_address=wallet_for(index),
                    email=email,
                    password_hash=hash_password(PASSWORD),
                    display_name=display_name,
                    bio="Synthetic hackathon demo account",
                )
                session.add(user)
                session.flush()
            else:
                user.email = email
                user.display_name = display_name
            users.append(user)
        (ACCOUNT_DIR / "accounts.csv").write_text(
            "email,password\n" + "\n".join(f"{u.email},{PASSWORD}" for u in users) + "\n",
            encoding="utf-8",
        )
        (ACCOUNT_DIR / "README.md").write_text(
            "These are local-only synthetic accounts for the hackathon demo.\n\nAll accounts use the same password shown in accounts.csv. Do not use these credentials outside the demo database.\n",
            encoding="utf-8",
        )

        specs = [
            (
                "NOAA buoy weather observations",
                "csv",
                "station_id, observed_at, air_temp_c, wave_height_m. Use UTC ISO-8601 timestamps, real station IDs, numeric measurements, no blank required fields, and at least two observations.",
                "Validate an NDBC-style observation table. Reject missing headers, malformed timestamps, blank required values, or nonnumeric measurements. Good files contain at least two coherent UTC observations and plausible units.",
            ),
            (
                "Street-sign image and location captions",
                "image_text",
                "One readable traffic sign image plus a companion caption naming sign type, road context, and approximate country. The sign must be visible and the caption must agree with the image.",
                "Check that one traffic sign is centered, readable, and consistent with the caption. Reject unrelated images or absent text. High quality means sharp sign edges, useful road context, and a specific matching caption.",
            ),
            (
                "Urban tree health photo notes",
                "image_text",
                "One street-tree image plus a concise note covering species or morphology, visible health indicators, and urban setting. Avoid faces and license plates.",
                "Evaluate whether the image shows one identifiable street tree and whether the note records observable canopy, trunk, and setting details. Reject non-tree images. Low quality is dark, distant, or vague; good quality is clear and specific.",
            ),
            (
                "USGS-style stream gauge readings",
                "csv",
                "station_id, observed_at, discharge_cfs, water_temp_c, pH. Use UTC ISO-8601 timestamps, numeric values, pH 0-14, and two or more rows per station.",
                "Reject absent columns, invalid dates, blank fields, impossible pH, or nonnumeric readings. Good data has repeated station observations, plausible discharge and temperature, and stable two-decimal pH.",
            ),
            (
                "Road-scene lane segmentation masks",
                "image_segmentation_text",
                "Submit an RGB road image, a flat-color PNG mask, and text naming the scene. Mask colors must be lane marking white, drivable road gray, and background black; image and mask dimensions must match.",
                "Require matching image/mask dimensions and a flat RGB mask using only black, gray, and white. Reject gradients, unrelated masks, or missing text. Good samples cover visible lane markings cleanly without painting the whole frame as road.",
            ),
        ]
        created_calls: list[DataCall] = []
        for offset, (title, dtype, criteria, prompt) in enumerate(specs):
            call = session.scalar(select(DataCall).where(DataCall.title == title))
            if call is None:
                call = DataCall(
                    caller_id=users[0].id,
                    title=title,
                    description=f"Synthetic demo collection inspired by public environmental and computer-vision data conventions. {criteria}",
                    data_type=dtype,
                    acceptance_criteria=criteria,
                    ai_evaluation_prompt=prompt,
                    csv_columns="station_id,observed_at,air_temp_c,wave_height_m"
                    if offset == 0
                    else (
                        "station_id,observed_at,discharge_cfs,water_temp_c,pH"
                        if offset == 3
                        else None
                    ),
                    csv_delimiter="," if dtype == "csv" else None,
                    csv_min_records=2 if dtype == "csv" else None,
                    csv_max_records=100 if dtype == "csv" else None,
                    csv_unique_column=None,
                    segmentation_mode="all" if dtype == "image_segmentation_text" else None,
                    review_mode="ai_assisted",
                    standard_reward=1_000_000,
                    high_reward=2_000_000,
                    max_acceptances=9,
                    deadline=utcnow() + timedelta(days=30),
                    status=CallStatus.OPEN,
                    escrow_call_id=9000 + offset,
                    funding_tx_hash="0x"
                    + hashlib.sha256(f"demo-funding-{offset}".encode()).hexdigest(),
                )
                session.add(call)
                session.flush()
                session.add(
                    CallLink(
                        call_id=call.id,
                        label="Research source notes",
                        url="https://www.noaa.gov/"
                        if dtype == "csv"
                        else "https://www.tensorflow.org/datasets/catalog/oxford_iiit_pet",
                    )
                )
            created_calls.append(call)

        for call_index, call in enumerate(created_calls):
            if not GENERATE_FIXTURES:
                session.execute(delete(Contribution).where(Contribution.call_id == call.id))
                continue
            if session.scalar(select(Contribution.id).where(Contribution.call_id == call.id).limit(9)) is not None:
                session.execute(delete(Contribution).where(Contribution.call_id == call.id))
            call_dir = DATA_DIR / f"call_{call.id:02d}_{call.title.lower().replace(' ', '_')[:35]}"
            for quality in ("invalid", "low", "good"):
                for replica in range(1, 4):
                    stem = f"{quality}_{replica}"
                    if call.data_type == "csv":
                        source = add_file(call_dir, stem + ".csv", "csv", call.title, quality)
                        companion = None
                        media_type = "text/csv"
                    else:
                        source = add_file(call_dir, stem + ".png", "image", call.title, quality)
                        companion = (
                            f"Synthetic {quality} sample for {call.title}."
                            if call.data_type == "image_text"
                            else f"Road scene {quality} sample; lane markings are represented in the accompanying mask."
                        )
                        media_type = "image/png"
                    digest = hashlib.sha256(source.read_bytes()).hexdigest()
                    if session.scalar(
                        select(Contribution).where(
                            Contribution.sha256 == digest, Contribution.call_id == call.id
                        )
                    ):
                        continue
                    contributor = users[(call_index * 3 + replica) % len(users)]
                    rejected = quality == "invalid"
                    stored_name = f"demo-{call.id}-{stem}{source.suffix}"
                    shutil.copyfile(source, settings.upload_dir / stored_name)
                    source_stored_name = None
                    source_original_name = None
                    source_hash = None
                    source_media = None
                    source_size = None
                    if call.data_type == "image_segmentation_text":
                        mask = call_dir / f"{stem}_mask.png"
                        mask_image = Image.new("RGB", (640, 400), (0, 0, 0))
                        mask_draw = ImageDraw.Draw(mask_image)
                        if quality != "invalid":
                            mask_draw.rectangle((180, 210, 460, 250), fill=(255, 255, 255))
                            mask_draw.rectangle((100, 250, 540, 360), fill=(128, 128, 128))
                        mask_image.save(mask)
                        source_stored_name = f"demo-{call.id}-{stem}_mask.png"
                        shutil.copyfile(mask, settings.upload_dir / source_stored_name)
                        source_original_name = mask.name
                        source_hash = hashlib.sha256(mask.read_bytes()).hexdigest()
                        source_media = "image/png"
                        source_size = mask.stat().st_size
                    session.add(
                        Contribution(
                            call_id=call.id,
                            contributor_id=contributor.id,
                            stored_filename=stored_name,
                            original_filename=source.name,
                            sha256=digest,
                            media_type=media_type,
                            size_bytes=source.stat().st_size,
                            companion_text=companion,
                            source_stored_filename=source_stored_name,
                            source_original_filename=source_original_name,
                            source_sha256=source_hash,
                            source_media_type=source_media,
                            source_size_bytes=source_size,
                            validation_summary="Pre-check failed: required fields or media structure is invalid."
                            if rejected
                            else "Pre-check passed; human review should inspect detail and usefulness.",
                            status=ContributionStatus.REJECTED
                            if rejected
                            else ContributionStatus.READY,
                            evaluation_progress=100,
                            evaluation_stage="Demo fixture evaluated",
                            ai_recommendation="reject"
                            if rejected
                            else ("unsure" if quality == "low" else "accept"),
                            ai_tier="standard" if quality != "good" else "high",
                            ai_explanation=f"Demo fixture labeled {quality}: the recommendation is seeded to make the review workflow visible.",
                            model_name="demo-seed",
                            final_decision="rejected" if rejected else None,
                        )
                    )
            existing_comments = session.scalars(
                select(Comment).where(Comment.call_id == call.id)
            ).all()
            prompts = discussion_prompts(call.title)
            if len(existing_comments) < 18:
                for prompt_index, prompt in enumerate(prompts):
                    root = Comment(
                        call_id=call.id,
                        author_id=users[(call_index + prompt_index) % len(users)].id,
                        body=prompt,
                    )
                    session.add(root)
                    session.flush()
                    if prompt_index % 2 == 0:
                        session.add(
                            Comment(
                                call_id=call.id,
                                author_id=users[(call_index + prompt_index + 3) % len(users)].id,
                                parent_id=root.id,
                                body=(
                                    "I see the trade-off. I would document that decision in the review notes "
                                    "and apply the same threshold to every contributor."
                                ),
                            )
                        )
        session.commit()
        print(f"Seeded {len(users)} demo accounts and {len(created_calls)} calls.")


if __name__ == "__main__":
    seed()
