"""Seed corpus of genuinely public-domain U.S. primary legal text (verbatim
constitutional provisions). The U.S. Constitution is a public-domain government work, so
these are real, citable sources - nothing is fabricated - giving the system authentic
material to ground answers in even offline.

Each record also carries accurate topical `keywords` (the provision's name and the subjects
it is well established to cover). These are factual descriptors, not invented law; they are
indexed alongside the verbatim text so natural-language questions still retrieve the right
provision. The viewer always shows the verbatim `text`, never the keywords.

For broader, current coverage (case law, regulations, statutes), enable the live government
sources (see app/rag/live_sources.py) or run scripts/ingest_courtlistener.py."""
from __future__ import annotations

from .store import Record

_BOR = "1791-12-15"   # Bill of Rights ratified
_CONST = "https://constitution.congress.gov/constitution"


def _amend(n: str) -> str:
    return f"{_CONST}/amendment-{n}/"


SEED_DOCS: list[Record] = [
    Record(
        id="usconst-amend-1",
        text=("Congress shall make no law respecting an establishment of religion, or "
              "prohibiting the free exercise thereof; or abridging the freedom of speech, "
              "or of the press; or the right of the people peaceably to assemble, and to "
              "petition the Government for a redress of grievances."),
        citation="U.S. Const. amend. I", source_id="usconst/amendment/1",
        source_url=_amend("1"), effective_date=_BOR,
        keywords=("First Amendment freedom of speech religion press assembly petition "
                  "establishment clause free exercise expression protest")),
    Record(
        id="usconst-amend-2",
        text=("A well regulated Militia, being necessary to the security of a free State, "
              "the right of the people to keep and bear Arms, shall not be infringed."),
        citation="U.S. Const. amend. II", source_id="usconst/amendment/2",
        source_url=_amend("2"), effective_date=_BOR,
        keywords=("Second Amendment right to keep and bear arms guns firearms militia "
                  "weapons gun rights")),
    Record(
        id="usconst-amend-3",
        text=("No Soldier shall, in time of peace be quartered in any house, without the "
              "consent of the Owner, nor in time of war, but in a manner to be prescribed "
              "by law."),
        citation="U.S. Const. amend. III", source_id="usconst/amendment/3",
        source_url=_amend("3"), effective_date=_BOR,
        keywords=("Third Amendment quartering of soldiers in homes during peace and war")),
    Record(
        id="usconst-amend-4",
        text=("The right of the people to be secure in their persons, houses, papers, and "
              "effects, against unreasonable searches and seizures, shall not be violated, "
              "and no Warrants shall issue, but upon probable cause, supported by Oath or "
              "affirmation, and particularly describing the place to be searched, and the "
              "persons or things to be seized."),
        citation="U.S. Const. amend. IV", source_id="usconst/amendment/4",
        source_url=_amend("4"), effective_date=_BOR,
        keywords=("Fourth Amendment unreasonable search and seizure warrant probable cause "
                  "privacy police stop arrest")),
    Record(
        id="usconst-amend-5",
        text=("No person shall be held to answer for a capital, or otherwise infamous "
              "crime, unless on a presentment or indictment of a Grand Jury, except in "
              "cases arising in the land or naval forces, or in the Militia, when in actual "
              "service in time of War or public danger; nor shall any person be subject for "
              "the same offence to be twice put in jeopardy of life or limb; nor shall be "
              "compelled in any criminal case to be a witness against himself, nor be "
              "deprived of life, liberty, or property, without due process of law; nor shall "
              "private property be taken for public use, without just compensation."),
        citation="U.S. Const. amend. V", source_id="usconst/amendment/5",
        source_url=_amend("5"), effective_date=_BOR,
        keywords=("Fifth Amendment due process self-incrimination right to remain silent "
                  "double jeopardy grand jury eminent domain just compensation takings")),
    Record(
        id="usconst-amend-6",
        text=("In all criminal prosecutions, the accused shall enjoy the right to a speedy "
              "and public trial, by an impartial jury of the State and district wherein the "
              "crime shall have been committed, which district shall have been previously "
              "ascertained by law, and to be informed of the nature and cause of the "
              "accusation; to be confronted with the witnesses against him; to have "
              "compulsory process for obtaining witnesses in his favor, and to have the "
              "Assistance of Counsel for his defence."),
        citation="U.S. Const. amend. VI", source_id="usconst/amendment/6",
        source_url=_amend("6"), effective_date=_BOR,
        keywords=("Sixth Amendment speedy public trial impartial jury right to counsel "
                  "confront witnesses criminal prosecution defense attorney")),
    Record(
        id="usconst-amend-7",
        text=("In Suits at common law, where the value in controversy shall exceed twenty "
              "dollars, the right of trial by jury shall be preserved, and no fact tried by "
              "a jury, shall be otherwise re-examined in any Court of the United States, "
              "than according to the rules of the common law."),
        citation="U.S. Const. amend. VII", source_id="usconst/amendment/7",
        source_url=_amend("7"), effective_date=_BOR,
        keywords=("Seventh Amendment civil jury trial common law suits twenty dollars")),
    Record(
        id="usconst-amend-8",
        text=("Excessive bail shall not be required, nor excessive fines imposed, nor cruel "
              "and unusual punishments inflicted."),
        citation="U.S. Const. amend. VIII", source_id="usconst/amendment/8",
        source_url=_amend("8"), effective_date=_BOR,
        keywords=("Eighth Amendment excessive bail excessive fines cruel and unusual "
                  "punishment sentencing")),
    Record(
        id="usconst-amend-9",
        text=("The enumeration in the Constitution, of certain rights, shall not be "
              "construed to deny or disparage others retained by the people."),
        citation="U.S. Const. amend. IX", source_id="usconst/amendment/9",
        source_url=_amend("9"), effective_date=_BOR,
        keywords=("Ninth Amendment unenumerated rights retained by the people")),
    Record(
        id="usconst-amend-10",
        text=("The powers not delegated to the United States by the Constitution, nor "
              "prohibited by it to the States, are reserved to the States respectively, or "
              "to the people."),
        citation="U.S. Const. amend. X", source_id="usconst/amendment/10",
        source_url=_amend("10"), effective_date=_BOR,
        keywords=("Tenth Amendment states rights reserved powers federalism")),
    Record(
        id="usconst-amend-13-s1",
        text=("Neither slavery nor involuntary servitude, except as a punishment for crime "
              "whereof the party shall have been duly convicted, shall exist within the "
              "United States, or any place subject to their jurisdiction."),
        citation="U.S. Const. amend. XIII, sec. 1", source_id="usconst/amendment/13/1",
        source_url=_amend("13"), effective_date="1865-12-06",
        keywords=("Thirteenth Amendment abolition of slavery involuntary servitude")),
    Record(
        id="usconst-amend-14-s1",
        text=("All persons born or naturalized in the United States, and subject to the "
              "jurisdiction thereof, are citizens of the United States and of the State "
              "wherein they reside. No State shall make or enforce any law which shall "
              "abridge the privileges or immunities of citizens of the United States; nor "
              "shall any State deprive any person of life, liberty, or property, without due "
              "process of law; nor deny to any person within its jurisdiction the equal "
              "protection of the laws."),
        citation="U.S. Const. amend. XIV, sec. 1", source_id="usconst/amendment/14/1",
        source_url=_amend("14"), effective_date="1868-07-09",
        keywords=("Fourteenth Amendment equal protection due process citizenship birthright "
                  "privileges immunities state action discrimination")),
    Record(
        id="usconst-amend-15-s1",
        text=("The right of citizens of the United States to vote shall not be denied or "
              "abridged by the United States or by any State on account of race, color, or "
              "previous condition of servitude."),
        citation="U.S. Const. amend. XV, sec. 1", source_id="usconst/amendment/15/1",
        source_url=_amend("15"), effective_date="1870-02-03",
        keywords=("Fifteenth Amendment voting rights race color cannot be denied the vote")),
    Record(
        id="usconst-amend-19",
        text=("The right of citizens of the United States to vote shall not be denied or "
              "abridged by the United States or by any State on account of sex. Congress "
              "shall have power to enforce this article by appropriate legislation."),
        citation="U.S. Const. amend. XIX", source_id="usconst/amendment/19",
        source_url=_amend("19"), effective_date="1920-08-18",
        keywords=("Nineteenth Amendment women's suffrage right to vote regardless of sex")),
    Record(
        id="usconst-amend-26-s1",
        text=("The right of citizens of the United States, who are eighteen years of age or "
              "older, to vote shall not be denied or abridged by the United States or by any "
              "State on account of age."),
        citation="U.S. Const. amend. XXVI, sec. 1", source_id="usconst/amendment/26/1",
        source_url=_amend("26"), effective_date="1971-07-01",
        keywords=("Twenty-sixth Amendment voting age eighteen years old right to vote")),
]
