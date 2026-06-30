"""Seed corpus of genuinely public-domain U.S. primary legal text (verbatim
constitutional provisions). Real, citable sources - nothing fabricated.

Each record also carries accurate topical `keywords` (the amendment's name and the
subjects it is well established to cover). These are factual descriptors, not invented
law; they are indexed alongside the verbatim text so that natural-language questions
(which often don't repeat the passage's exact words) still retrieve the right provision.
The viewer always shows the verbatim `text`, never the keywords."""
from __future__ import annotations

from .store import Record

SEED_DOCS: list[Record] = [
    Record(
        id="usconst-amend-1",
        text=("Congress shall make no law respecting an establishment of religion, or "
              "prohibiting the free exercise thereof; or abridging the freedom of speech, "
              "or of the press; or the right of the people peaceably to assemble, and to "
              "petition the Government for a redress of grievances."),
        citation="U.S. Const. amend. I",
        source_id="usconst/amendment/1",
        source_url="https://constitution.congress.gov/constitution/amendment-1/",
        effective_date="1791-12-15",
        keywords=("First Amendment freedom of speech religion press assembly petition "
                  "establishment clause free exercise expression protest"),
    ),
    Record(
        id="usconst-amend-4",
        text=("The right of the people to be secure in their persons, houses, papers, and "
              "effects, against unreasonable searches and seizures, shall not be violated, "
              "and no Warrants shall issue, but upon probable cause, supported by Oath or "
              "affirmation, and particularly describing the place to be searched, and the "
              "persons or things to be seized."),
        citation="U.S. Const. amend. IV",
        source_id="usconst/amendment/4",
        source_url="https://constitution.congress.gov/constitution/amendment-4/",
        effective_date="1791-12-15",
        keywords=("Fourth Amendment unreasonable search and seizure warrant probable cause "
                  "privacy police stop arrest"),
    ),
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
        citation="U.S. Const. amend. V",
        source_id="usconst/amendment/5",
        source_url="https://constitution.congress.gov/constitution/amendment-5/",
        effective_date="1791-12-15",
        keywords=("Fifth Amendment due process self-incrimination right to remain silent "
                  "double jeopardy grand jury eminent domain just compensation takings"),
    ),
    Record(
        id="usconst-amend-6",
        text=("In all criminal prosecutions, the accused shall enjoy the right to a speedy "
              "and public trial, by an impartial jury of the State and district wherein the "
              "crime shall have been committed, which district shall have been previously "
              "ascertained by law, and to be informed of the nature and cause of the "
              "accusation; to be confronted with the witnesses against him; to have "
              "compulsory process for obtaining witnesses in his favor, and to have the "
              "Assistance of Counsel for his defence."),
        citation="U.S. Const. amend. VI",
        source_id="usconst/amendment/6",
        source_url="https://constitution.congress.gov/constitution/amendment-6/",
        effective_date="1791-12-15",
        keywords=("Sixth Amendment speedy public trial impartial jury right to counsel "
                  "confront witnesses criminal prosecution defense attorney"),
    ),
    Record(
        id="usconst-amend-14-s1",
        text=("All persons born or naturalized in the United States, and subject to the "
              "jurisdiction thereof, are citizens of the United States and of the State "
              "wherein they reside. No State shall make or enforce any law which shall "
              "abridge the privileges or immunities of citizens of the United States; nor "
              "shall any State deprive any person of life, liberty, or property, without due "
              "process of law; nor deny to any person within its jurisdiction the equal "
              "protection of the laws."),
        citation="U.S. Const. amend. XIV, sec. 1",
        source_id="usconst/amendment/14/1",
        source_url="https://constitution.congress.gov/constitution/amendment-14/",
        effective_date="1868-07-09",
        keywords=("Fourteenth Amendment equal protection due process citizenship birthright "
                  "privileges immunities state action discrimination"),
    ),
]
