import sys
import os
from pyarrow.parquet import ParquetFile
from rich.syntax import Syntax
from textual.app import App, ComposeResult
from textual.widgets import Static, Footer
from textual import events
import pyperclip


class ParquetApp(App[str]):

    CSS_PATH = "style.css"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("←", "previous", "Previous"),
        ("→", "next", "Next"),
        ("s", "schema", "Schema"),
        ("c", "copy", "Copy"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(id="info")
        yield Static(id="json")
        yield Footer()

    def update_group(self):
        self.group = self.parquet_file.read_row_group(self.group_index, columns=None).to_pandas()

    def read_line(self):
        if self.row_index - self.group_offset < len(self.group):
            row = self.group.iloc[self.row_index - self.group_offset, ]
            return row.to_json(indent=2)
        else:
            return None

    def show_row(self):
        info_view = self.query_one("#info", Static)
        info = f"{self.file_path} - group {self.group_index + 1}/{self.parquet_file.num_row_groups} - row {self.row_index + 1}/{self.parquet_file.metadata.num_rows}"
        info_view.update(info)

        json_view = self.query_one("#json", Static)
        row = self.read_line()
        if row is not None:
            syntax = Syntax(row, "json", theme="github-dark", line_numbers=True, word_wrap=False, indent_guides=True)
            self.content = row
        else:
            syntax = Syntax("", "text", theme="github-dark", line_numbers=True, word_wrap=False, indent_guides=True)
            self.content = ""
        json_view.update(syntax)

    def toggle_schema(self):
        if self.schema is None:
            json_view = self.query_one("#json", Static)
            self.schema = "\n".join(str(self.parquet_file.schema).splitlines(keepends=False)[1:])
            syntax = Syntax(self.schema, "yaml", theme="github-dark", line_numbers=True, word_wrap=False, indent_guides=True)
            self.content = self.schema
            json_view.update(syntax)
        else:
            self.schema = None
            self.show_row()

    def previous(self):
        self.row_index = self.row_index - 1 if self.row_index > 0 else 0
        if self.row_index < self.group_offset:
            self.group_index = self.group_index - 1
            self.group_offset = self.group_offset - self.group.shape[0]
            self.update_group()
        self.show_row()

    def next(self):
        if self.row_index < self.parquet_file.metadata.num_rows - 1:
            self.row_index = self.row_index + 1
            if self.row_index >= self.group_offset + self.group.shape[0]:
                self.group_index = self.group_index + 1
                self.group_offset = self.group_offset + self.group.shape[0]
                self.update_group()
            self.show_row()

    def copy(self):
        pyperclip.copy(self.content)

    def on_key(self, event: events.Key) -> None:
        if event.key == "left":
            self.previous()
        elif event.key == "right":
            self.next()
        elif event.key == "s":
            self.toggle_schema()
        elif event.key == "c":
            self.copy()

    def on_mount(self) -> None:
        self.group = None
        self.group_index = 0
        self.group_offset = 0
        self.row_index = 0
        self.file_path = sys.argv[1]
        if not os.path.isfile(self.file_path):
            sys.exit(f"No such file: {self.file_path}")
        try:
            self.parquet_file = ParquetFile(os.path.expanduser(self.file_path))
        except Exception:
            sys.exit(f"Error reading file {self.file_path}")
        self.schema = None
        self.update_group()
        self.show_row()


def main():
    app = ParquetApp()
    app.run()


if __name__ == "__main__":
    main()
