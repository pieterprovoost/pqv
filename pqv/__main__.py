import sys
import os
from pyarrow.parquet import ParquetFile
from rich.syntax import Syntax
from textual.app import App, ComposeResult
from textual.widgets import Static, Footer
from textual import events
import pyperclip
import json
from datetime import datetime


def parse_if_json(input: str):
    try:
        parsed = json.loads(input)
        return parsed
    except ValueError:
        return input


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return str(obj)
        if isinstance(obj, bytes):
            return obj.hex()
        return super(CustomEncoder, self).default(obj)


class ParquetReader:

    def __init__(self, file_path: str):

        if not os.path.isfile(file_path):
            sys.exit(f"No such file: {file_path}")
        try:
            self.parquet_file = ParquetFile(os.path.expanduser(file_path))
        except Exception:
            sys.exit(f"Error reading file {file_path}")

        self.file_path = file_path
        self.group_stack = []
        self.group = None
        self.row_index = 0
        self.group_offset = 0
        self.row_group = ""

        self.schema = "\n".join(str(self.parquet_file.schema).splitlines(keepends=False)[1:])
        if self.parquet_file.metadata.metadata is not None:
            self.metadata = json.dumps({k.decode(): parse_if_json(v.decode()) for k, v in self.parquet_file.metadata.metadata.items()}, indent=2)
        else:
            self.metadata = ""

        self.read_group()

    def group_index(self):
        return len(self.group_stack)

    def read_group(self):
        row_group_index = len(self.group_stack)
        self.group = self.parquet_file.read_row_group(row_group_index, columns=None)
        row_group_info = self.parquet_file.metadata.row_group(row_group_index)
        self.row_group_info = json.dumps(row_group_info.to_dict(), indent=2, cls=CustomEncoder)

    def read_line(self):
        if self.row_index - self.group_offset < len(self.group):
            row_dict = dict([(k, v[0]) for k, v in self.group.slice(self.row_index - self.group_offset, 1).to_pydict().items()])
            json_str = json.dumps(row_dict, indent=2, cls=CustomEncoder)
            return json_str
        else:
            return None

    def check_group_needs_update(self):
        if self.row_index < self.group_offset:
            shape = self.group_stack.pop()
            self.read_group()
            self.group_offset = self.group_offset - shape
        elif self.row_index >= self.group_offset + self.group.shape[0]:
            self.group_stack.append(self.group.shape[0])
            self.group_offset = self.group_offset + self.group.shape[0]
            self.read_group()

    def previous(self):
        self.set_row(self.row_index - 1 if self.row_index > 0 else 0)

    def next(self):
        if self.row_index < self.parquet_file.metadata.num_rows - 1:
            self.set_row(self.row_index + 1)

    def next_group(self):
        if self.group_index() < self.parquet_file.metadata.num_row_groups - 1:
            self.set_row(self.group_offset + self.group.shape[0])
        else:
            self.set_row(self.parquet_file.metadata.num_rows - 1)

    def previous_group(self):
        if self.group_index() > 0:
            self.set_row(self.group_offset - self.group_stack[~0])
        else:
            self.set_row(0)

    def set_row(self, row_index: int):
        self.row_index = row_index
        self.check_group_needs_update()


class ParquetApp(App[str]):

    CSS_PATH = "style.css"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("←", "previous", "Previous"),
        ("→", "next", "Next"),
        ("⇧", "shift", "Group"),
        ("s", "schema", "Schema"),
        ("m", "metadata", "Metadata"),
        ("r", "rgmetadata", "Group metadata"),
        ("c", "copy", "Copy"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(id="info")
        yield Static(id="json")
        yield Footer()

    def show_row(self):
        self.state = "row"
        info_view = self.query_one("#info", Static)
        info = f"{self.reader.file_path} - group {self.reader.group_index() + 1}/{self.reader.parquet_file.num_row_groups} - row {self.reader.row_index + 1}/{self.reader.parquet_file.metadata.num_rows}"
        info_view.update(info)

        json_view = self.query_one("#json", Static)
        row = self.reader.read_line()
        if row is not None:
            syntax = Syntax(row, "json", theme="github-dark", line_numbers=True, word_wrap=False, indent_guides=True)
            self.content = row
        else:
            syntax = Syntax("", "text", theme="github-dark", line_numbers=True, word_wrap=False, indent_guides=True)
            self.content = ""
        json_view.update(syntax)

    def toggle_schema(self):
        if self.state != "schema":
            self.state = "schema"
            json_view = self.query_one("#json", Static)
            syntax = Syntax(self.reader.schema, "yaml", theme="github-dark", line_numbers=True, word_wrap=False, indent_guides=True)
            self.content = self.reader.schema
            json_view.update(syntax)
        else:
            self.show_row()

    def toggle_metadata(self):
        if self.state != "metadata":
            self.state = "metadata"
            json_view = self.query_one("#json", Static)
            syntax = Syntax(self.reader.metadata, "yaml", theme="github-dark", line_numbers=True, word_wrap=False, indent_guides=True)
            self.content = self.reader.metadata
            json_view.update(syntax)
        else:
            self.show_row()

    def toggle_row_group_info(self):
        if self.state != "rowgroup":
            self.state = "rowgroup"
            json_view = self.query_one("#json", Static)
            syntax = Syntax(self.reader.row_group_info, "yaml", theme="github-dark", line_numbers=True, word_wrap=False, indent_guides=True)
            self.content = self.reader.row_group_info
            json_view.update(syntax)
        else:
            self.show_row()

    def copy(self):
        pyperclip.copy(self.content)

    def previous(self):
        self.reader.previous()
        self.show_row()

    def next(self):
        self.reader.next()
        self.show_row()

    def previous_group(self):
        self.reader.previous_group()
        self.show_row()

    def next_group(self):
        self.reader.next_group()
        self.show_row()

    def on_key(self, event: events.Key) -> None:
        if event.key == "left":
            self.previous()
        elif event.key == "right":
            self.next()
        elif event.key == "shift+left":
            self.previous_group()
        elif event.key == "shift+right":
            self.next_group()
        elif event.key == "s":
            self.toggle_schema()
        elif event.key == "m":
            self.toggle_metadata()
        elif event.key == "g":
            self.toggle_row_group_info()
        elif event.key == "c":
            self.copy()

    def on_mount(self) -> None:
    
        self.reader = ParquetReader(sys.argv[1])
        self.show_row()
    

def main():
    app = ParquetApp()
    app.run()


if __name__ == "__main__":
    main()
