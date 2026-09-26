"""
Idempotent seed script (§2.3): running it twice must not duplicate rows.
We derive each complaint's id deterministically (uuid5 of its text) and use
INSERT ... ON CONFLICT (id) DO NOTHING, so a second run is a safe no-op.

Run with:  python -m scripts.seed
"""
import asyncio
import uuid

from sqlalchemy.dialects.postgresql import insert

from app.database import SessionLocal
from app.models import Complaint
from app.schemas import Category, Priority, Status

SEED_NAMESPACE = uuid.UUID("12345678-1234-5678-1234-567812345678")

# (text, location, category, priority)
COMPLAINTS: list[tuple[str, str, Category, Priority]] = [
    ("Burst water main flooding Street 12 since fajr, water entering ground floors", "Street 12, G-9, Islamabad", Category.water, Priority.high),
    ("Hamari gali mein pichle teen din se paani ka pipe leak ho raha hai, sarak par kichar ban gaya hai", "Street 4, I-8/3, Islamabad", Category.water, Priority.normal),
    ("Water supply bilkul band hai do din se, tanker bhi nahi aa raha", "Sector F-10, Islamabad", Category.water, Priority.high),
    ("Sewage water mix ho raha hai peene wale paani ki line mein, bohat khatarnak hai", "Street 9, G-11, Islamabad", Category.water, Priority.high),
    ("Naali ka paani ghar ke samne khara hai, machar bohat ho gaye hain", "Model Town Block C, Lahore", Category.water, Priority.normal),
    ("WAPDA transformer sparking near the mosque, bohat khatarnak lag raha hai, bachay khelte hain wahan", "Sector F-7, Islamabad", Category.electricity, Priority.high),
    ("Bijli ki tar road par latak rahi hai storm ke baad, koi bhi zakhmi ho sakta hai", "Johar Town, Lahore", Category.electricity, Priority.high),
    ("Ghanton se light nahi hai humare mohalle mein, load shedding schedule follow nahi ho raha", "Street 22, I-10, Islamabad", Category.electricity, Priority.normal),
    ("Meter ke pass short circuit ho raha hai, dhuwan bhi nikla tha kal raat", "Gulshan-e-Iqbal, Karachi", Category.electricity, Priority.high),
    ("Voltage bohat kam aa raha hai is hafte se, appliances kharab ho rahe hain", "DHA Phase 5, Lahore", Category.electricity, Priority.normal),
    ("Garbage not collected from our gali for one week, bohat badbu aa rahi hai aur kutte bhi aa gaye hain", "Street 4, I-8, Islamabad", Category.sanitation, Priority.normal),
    ("Kachra truck nahi aaya do hafton se, poora gali kachre se bhar gayi hai", "Sector 15-A, Karachi", Category.sanitation, Priority.high),
    ("Open drain overflow ho raha hai barish ke baad, sadak par ganda paani bahta hai", "Rehmanpura, Lahore", Category.sanitation, Priority.high),
    ("Dead animal laying near the dumpster for two days, sakht badbu hai", "Sector G-6, Islamabad", Category.sanitation, Priority.high),
    ("Sarkari kachra container hafton se overflow ho raha hai, koi utha kar nahi le ja raha", "Satellite Town, Rawalpindi", Category.sanitation, Priority.normal),
    ("Bara sa pothole ban gaya hai road pe, bike phis jati hai barish mein", "Link Road, Gulberg, Lahore", Category.roads, Priority.normal),
    ("Road completely damaged after construction, gaddon ki wajah se traffic jam ho jata hai roz", "Main Boulevard, DHA, Lahore", Category.roads, Priority.normal),
    ("Footpath tuta hua hai, wheelchair walon ke liye chalna mushkil hai", "Blue Area, Islamabad", Category.roads, Priority.normal),
    ("Speed breaker bina paint ke hai, raat ko nazar nahi aata, accident ho chuka hai", "University Road, Peshawar", Category.roads, Priority.high),
    ("Sarak dhas gayi hai underground pipe leak ki wajah se, bara gaddha ban gaya hai", "Street 7, F-11, Islamabad", Category.roads, Priority.high),
    ("Streetlight on main road not working since three days, andhera rehta hai raat ko, chori ka dar hai", "Main Boulevard, DHA, Lahore", Category.streetlights, Priority.normal),
    ("Poora mohalla andhere mein hai, tamam khambay kaam nahi kar rahe", "Sector I-9, Islamabad", Category.streetlights, Priority.normal),
    ("Streetlight khamba giri hui hai sadak par, koi bhi takra sakta hai", "Shahrah-e-Faisal, Karachi", Category.streetlights, Priority.high),
    ("Park ki lights band hain, shaam ke baad koi nahi jata safety ki wajah se", "F-8 Markaz, Islamabad", Category.streetlights, Priority.normal),
    ("New streetlight lagi thi par ek hafte mein hi kharab ho gayi", "Bahria Town, Rawalpindi", Category.streetlights, Priority.low),
    ("Stray dogs ka jhund gali mein ghoomta hai, bachon ko school jaate hue dar lagta hai", "Street 18, G-13, Islamabad", Category.other, Priority.normal),
    ("Construction site pe safety barrier nahi hai, log gir sakte hain raat ko", "Bahadurabad, Karachi", Category.other, Priority.high),
    ("Park mein jhoole tootay huay hain, bachon ko chot lag sakti hai", "Fatima Jinnah Park, Lahore", Category.other, Priority.normal),
    ("Noise pollution roz raat ko wedding hall se, neend nahi aati", "Askari 10, Lahore", Category.other, Priority.low),
    ("Illegal encroachment ne footpath completely block kar diya hai", "Saddar, Rawalpindi", Category.other, Priority.normal),
    ("Water tanker mafia overcharge kar raha hai, sarkari rate se teen guna zyada", "Sector G-15, Islamabad", Category.water, Priority.normal),
    ("Gas leak smell aa rahi hai kal se hamari gali mein, bohat khatarnak ho sakta hai", "Model Colony, Karachi", Category.other, Priority.high),
]


def _make_summary(text: str) -> str:
    summary = " ".join(text.strip().split())
    return summary[:137] + "..." if len(summary) > 140 else summary


async def seed():
    async with SessionLocal() as session:
        inserted = 0
        for text, location, category, priority in COMPLAINTS:
            complaint_id = uuid.uuid5(SEED_NAMESPACE, text)
            stmt = (
                insert(Complaint)
                .values(
                    id=complaint_id,
                    text=text,
                    location=location,
                    category=category,
                    priority=priority,
                    status=Status.open,
                    ai_summary=_make_summary(text),
                    triaged_by="rules",
                    triage_latency_ms=5,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
            result = await session.execute(stmt)
            inserted += result.rowcount or 0
        await session.commit()
    print(f"Seed complete: {inserted} new rows inserted, {len(COMPLAINTS) - inserted} already present.")


if __name__ == "__main__":
    asyncio.run(seed())
