"""
Quick sanity-check / summary report for the generated dataset.

Usage:
    python -m backend.datasets.inspect_data
"""

from collections import Counter

from backend.database.config import SessionLocal
from backend.database.models import (
    Person, Crime, FIR, Location, PersonCrimeLink, PersonRole,
    PersonAssociation, BankAccount, Transaction, CrimeType, PersonAlias,
)


def main():
    s = SessionLocal()
    try:
        n_persons = s.query(Person).count()
        n_crimes = s.query(Crime).count()
        n_firs = s.query(FIR).count()
        n_links = s.query(PersonCrimeLink).count()
        n_assoc = s.query(PersonAssociation).count()
        n_aliases = s.query(PersonAlias).count()

        print("=== SHERLOCK Dataset Summary ===")
        print(f"Persons:       {n_persons}")
        print(f"  with aliases: {s.query(PersonAlias.person_id).distinct().count()}")
        print(f"Crimes:        {n_crimes}")
        print(f"FIRs:          {n_firs}")
        print(f"Person links:  {n_links}")
        print(f"Associations:  {n_assoc}")
        print(f"Aliases:       {n_aliases}")

        print("\nCrime type distribution:")
        for ctype, count in Counter(c.type for c in s.query(Crime).all()).most_common():
            print(f"  {ctype.value:20s} {count}")

        print("\nBurglary by district / month (looking for festival-season spikes):")
        burglaries = s.query(Crime).filter_by(type=CrimeType.BURGLARY).all()
        by_district_month = Counter((c.location.district, c.timestamp.month) for c in burglaries)
        for (district, month), count in sorted(by_district_month.items(), key=lambda x: -x[1])[:10]:
            print(f"  {district:20s} month={month:2d}  count={count}")

        print("\nTop 5 repeat-offender candidates (most ACCUSED links):")
        accused = s.query(PersonCrimeLink).filter_by(role=PersonRole.ACCUSED).all()
        counts = Counter(l.person_id for l in accused)
        for person_id, count in counts.most_common(5):
            person = s.get(Person, person_id)
            print(f"  {person.name:25s} (id={person_id}) -> {count} accused links")

        print("\nMoney-mule fraud ring:")
        mule_accounts = s.query(BankAccount).filter_by(is_flagged_mule=True).all()
        print(f"  Flagged accounts: {len(mule_accounts)}")
        sus = s.query(Transaction).filter_by(is_suspicious=True).all()
        print(f"  Suspicious transactions: {len(sus)}, total = {sum(t.amount for t in sus):,.2f}")

    finally:
        s.close()


if __name__ == "__main__":
    main()
