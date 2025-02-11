
#!/usr/bin/env python
# coding: utf-8

# Copyright (c) Saga Inc.
# Distributed under the terms of the GPL License.
from typing import Dict, List, Tuple

from mitosheet.code_chunks.code_chunk import CodeChunk
from mitosheet.state import State
from mitosheet.transpiler.transpile_utils import TAB, column_header_to_transpiled_code

from mitosheet.transpiler.transpile_utils import param_dict_to_code

# This is a helper function that generates the code for formatting the excel sheet
def get_format_code(state: State) -> list:
    code = []
    formats = state.df_formats
    for sheet_name, format in zip(state.df_names, formats):
        # If there is no formatting, we skip trying to access the colors
        params = {
            'header_background_color': format.get('headers', {}).get('backgroundColor'),
            'header_font_color': format.get('headers', {}).get('color'),
            'even_background_color': format.get('rows', {}).get('even', {}).get('backgroundColor'),
            'even_font_color': format.get('rows', {}).get('even', {}).get('color'),
            'odd_background_color': format.get('rows', {}).get('odd', {}).get('backgroundColor'),
            'odd_font_color': format.get('rows', {}).get('odd', {}).get('color'),
        }
        param_dict = {
            key: value for key, value in params.items()
            if value is not None
        }
        if param_dict == {}:
            continue

        params_code = param_dict_to_code(param_dict, tab_level=1)
        code.append(f'{TAB}add_formatting_to_excel_sheet(writer, "{sheet_name}", {params_code})')
    return code


class ExportToFileCodeChunk(CodeChunk):

    def __init__(self, prev_state: State, post_state: State, export_type: str, file_name: str, sheet_index_to_export_location: Dict[int, str]):
        super().__init__(prev_state, post_state)
        self.export_type = export_type
        self.file_name = file_name
        self.sheet_index_to_export_location = sheet_index_to_export_location

    def get_display_name(self) -> str:
        return 'Export To File'

    def get_description_comment(self) -> str:
        return f"Exports {len(self.sheet_index_to_export_location)} to file {self.file_name}"

    def get_code(self) -> Tuple[List[str], List[str]]:
        if self.export_type == 'csv':
            return [
                f"{self.post_state.df_names[sheet_index]}.to_csv(r{column_header_to_transpiled_code(export_location)}, index=False)"
                for sheet_index, export_location in self.sheet_index_to_export_location.items()
            ], []
        elif self.export_type == 'excel':
            return [f"with pd.ExcelWriter(r{column_header_to_transpiled_code(self.file_name)}, engine=\"openpyxl\") as writer:"] + [
                f'{TAB}{self.post_state.df_names[sheet_index]}.to_excel(writer, sheet_name="{export_location}", index={False})'
                for sheet_index, export_location in self.sheet_index_to_export_location.items()
            ] + get_format_code(self.post_state), ['import pandas as pd']
        else:
            raise ValueError(f'Not a valid file type: {self.export_type}')
        
    def get_parameterizable_params(self) -> List[Tuple[str, str, str]]:
        if self.export_type == 'csv':
            return [
                (f"r{column_header_to_transpiled_code(export_location)}", 'file_name', 'CSV export file path') for export_location in self.sheet_index_to_export_location.values()
            ]
        elif self.export_type == 'excel':
            return [(f"r{column_header_to_transpiled_code(self.file_name)}", 'file_name', 'Excel export file path')]
        else:
            raise ValueError(f'Not a valid file type: {self.export_type}')
