import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from src.crunchyroll.models import SeriesSummary
from .base import BaseExporter, ExportResult


class MALXMLExporter(BaseExporter):
    """
    Exports watch history to MAL-compatible XML format.
    Importable at myanimelist.net/import.php and other sites that accept MAL XML.
    """

    def __init__(self, output_path: str | Path = "data/animelist.xml"):
        self.output_path = Path(output_path)

    def export(self, series: list[SeriesSummary]) -> ExportResult:
        result = ExportResult()
        root = ET.Element("myanimelist")

        info = ET.SubElement(root, "myinfo")
        ET.SubElement(info, "user_export_type").text = "1"
        ET.SubElement(info, "user_total_anime").text = str(len(series))

        for s in series:
            node = ET.SubElement(root, "anime")
            ET.SubElement(node, "series_animedb_id").text = ""
            ET.SubElement(node, "series_title").text = s.series_title
            ET.SubElement(node, "series_type").text = "TV"
            ET.SubElement(node, "series_episodes").text = "0"
            ET.SubElement(node, "my_id").text = "0"
            ET.SubElement(node, "my_watched_episodes").text = str(s.max_episode)
            ET.SubElement(node, "my_start_date").text = "0000-00-00"
            ET.SubElement(node, "my_finish_date").text = "0000-00-00"
            ET.SubElement(node, "my_score").text = "0"
            status = "Completed" if s.max_episode > 0 else "Plan to Watch"
            ET.SubElement(node, "my_status").text = status
            ET.SubElement(node, "update_on_import").text = "1"
            result.updated.append(s.series_title)

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        with open(self.output_path, "wb") as f:
            f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
            tree.write(f, encoding="utf-8", xml_declaration=False)

        return result
