"""Command line entry point:  python -m seed --size small --seed 42"""

import argparse
import sys

from app.database import create_db_engine
from app.models import Base
from seed.config import AVAILABLE_DEFECTS, DEFAULT_SEED, DEFAULT_SIZE, SIZES
from seed.defects import parse_defects
from seed.generators import build_dataset
from seed.writer import write_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m seed",
        description="Fill the CargaExpress database with reproducible mock data.",
    )
    parser.add_argument("--size", choices=list(SIZES), default=DEFAULT_SIZE,
                        help="data volume (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help="number that makes the data reproducible (default: %(default)s)")
    parser.add_argument("--defects", default="",
                        help="comma-separated data-quality defects. Available: "
                             + ", ".join(AVAILABLE_DEFECTS))
    parser.add_argument("--database-url", default=None,
                        help="database URL (default: DATABASE_URL variable or the local Docker database)")
    parser.add_argument("--reset", action="store_true",
                        help="DANGER: drop and recreate the CargaExpress tables before seeding")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        defects = parse_defects(args.defects)
    except ValueError as error:
        parser.error(str(error))  # prints the message and exits with code 2

    engine = create_db_engine(args.database_url)
    try:
        if args.reset:
            print("WARNING: --reset is on. Dropping the CargaExpress tables...")
            Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)  # creates only the tables that are missing

        dataset = build_dataset(args.size, args.seed, defects)
        report = write_dataset(engine, dataset)
    finally:
        engine.dispose()

    print(f"Seed finished. size={args.size} seed={args.seed} defects={','.join(defects) or 'none'}")
    print(f"{'table':<22}{'in dataset':>12}{'inserted':>10}{'already there':>15}")
    for table, total, inserted in report:
        print(f"{table:<22}{total:>12}{inserted:>10}{total - inserted:>15}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
