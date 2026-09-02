import csv
import os
import webbrowser

import click
from tabulate import tabulate

from .pipeline import create_zdr_from_rally, run_comparison
from .report import build_html


def _run_comparison():
    return run_comparison(on_progress=click.echo)


def _print_missing(missing_in_zdr):
    if not missing_in_zdr:
        click.echo("\nNo missing ZDR defects — every open Rally defect has a ZDR counterpart.")
        return
    rows = [
        [i + 1, d["id"], d["state"], d["severity"] or "-", d["owner"] or "-", d["name"][:80]]
        for i, d in enumerate(missing_in_zdr)
    ]
    click.echo(f"\n{len(missing_in_zdr)} Rally defect(s) missing a ZDR ticket:\n")
    click.echo(tabulate(rows, headers=["#", "Rally ID", "State", "Severity", "Owner", "Name"]))


@click.group()
def cli():
    """Compare and sync open defects between Rally and ZDR."""


@cli.command()
@click.option("--csv-out", "csv_out", default=None, help="Write the full comparison to a CSV file.")
@click.option(
    "--html-out",
    "html_out",
    default="reports/comparison.html",
    help="Write an interactive HTML report you can open in a browser. Pass '' to skip.",
)
@click.option("--open-html", "open_html", is_flag=True, help="Open the HTML report in your browser when done.")
def compare(csv_out, html_out, open_html):
    """Compare open defects between Rally and ZDR (read-only)."""
    rally_defects, zdr_defects, result = _run_comparison()

    click.echo(f"\nMatched: {len(result['matched'])}")
    _print_missing(result["missing_in_zdr"])

    if result["orphaned_in_zdr"]:
        click.echo(
            f"\n{len(result['orphaned_in_zdr'])} open ZDR ticket(s) reference a Rally ID "
            "that is no longer open in Rally (may be closed/rejected there, or a typo):"
        )
        rows = [[i["key"], i["rally_id"], i["summary"][:80]] for i in result["orphaned_in_zdr"]]
        click.echo(tabulate(rows, headers=["ZDR Key", "Rally ID", "Summary"]))

    if csv_out:
        with open(csv_out, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["rally_id", "state", "severity", "owner", "name", "zdr_status"])
            for m in result["matched"]:
                writer.writerow(
                    [
                        m["rally"]["id"],
                        m["rally"]["state"],
                        m["rally"]["severity"],
                        m["rally"]["owner"],
                        m["rally"]["name"],
                        ", ".join(z["status"] for z in m["zdr"]),
                    ]
                )
            for d in result["missing_in_zdr"]:
                writer.writerow([d["id"], d["state"], d["severity"], d["owner"], d["name"], "MISSING"])
        click.echo(f"\nWrote comparison to {csv_out}")

    if html_out:
        os.makedirs(os.path.dirname(html_out) or ".", exist_ok=True)
        with open(html_out, "w") as f:
            f.write(build_html(result, len(rally_defects), len(zdr_defects)))
        abs_path = os.path.abspath(html_out)
        click.echo(f"\nWrote HTML report to {abs_path}")
        if open_html:
            webbrowser.open(f"file://{abs_path}")


@cli.command()
def sync():
    """Compare, then interactively create ZDR tickets for Rally defects missing one."""
    _, _, result = _run_comparison()
    missing = result["missing_in_zdr"]
    _print_missing(missing)
    if not missing:
        return

    selection = click.prompt(
        "\nEnter numbers to create in ZDR (e.g. 1,3,5), 'all', or press Enter to skip",
        default="",
        show_default=False,
    )
    if not selection.strip():
        click.echo("No tickets created.")
        return

    if selection.strip().lower() == "all":
        to_create = missing
    else:
        indices = [int(x.strip()) - 1 for x in selection.split(",") if x.strip()]
        to_create = [missing[i] for i in indices if 0 <= i < len(missing)]

    if not click.confirm(f"Create {len(to_create)} ZDR ticket(s)?"):
        click.echo("Cancelled.")
        return

    created = []
    for defect in to_create:
        key, attached, attach_errors = create_zdr_from_rally(defect, on_progress=click.echo)
        created.append((defect["id"], key))
        if attach_errors:
            click.echo(f"    attachment errors: {'; '.join(attach_errors)}")

    click.echo(f"\nCreated {len(created)} ZDR ticket(s).")


if __name__ == "__main__":
    cli()
