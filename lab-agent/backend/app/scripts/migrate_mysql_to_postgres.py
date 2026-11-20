"""Legacy full-table migration is disabled by the LabOps 1.0 data policy.

The original MySQL database remains untouched. Users and resources have
separate guarded migration commands; historical reservations stay in MySQL.
"""


def main():
    raise SystemExit(
        "The legacy all-table importer is disabled. Use migrate_mysql_users "
        "or migrate_mysql_resources for the approved tables; reservations stay in MySQL."
    )


if __name__ == "__main__":
    main()
