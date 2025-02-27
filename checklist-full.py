from typing import Any, Generic, Sequence, TypeVar

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import AnyFormattedText, StyleAndTextTuples, to_formatted_text, HTML
from prompt_toolkit.formatted_text.utils import fragment_list_to_text
from prompt_toolkit.key_binding.bindings.focus import focus_next, focus_previous
from prompt_toolkit.key_binding.defaults import load_key_bindings
from prompt_toolkit.key_binding.key_bindings import KeyBindings, merge_key_bindings
from prompt_toolkit.key_binding.key_processor import KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Container, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.margins import ConditionalMargin, ScrollbarMargin
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from prompt_toolkit.styles import BaseStyle, Style
from prompt_toolkit.widgets import Label  # ,CheckboxList


T = TypeVar("T")
E = KeyPressEvent


# copied from /home/ubuntu/vunv/lib/python3.11/site-packages/prompt_toolkit/widgets/base.py
class MyChecklist(Generic[T]):
    """
    Common code for `RadioList` and `CheckboxList`.
    """

    open_character = "["
    close_character = "]"
    container_style = "class:checkbox-list"
    default_style = "class:checkbox"
    selected_style = "class:checkbox-selected"
    checked_style = "class:checkbox-checked"
    show_scrollbar = True

    def __init__(
        self,
        values: Sequence[tuple[T, AnyFormattedText]],
        default_values: Sequence[T] | None = None,
    ) -> None:
        assert len(values) > 0
        default_values = default_values or []

        self.values = values

        keys: list[T] = [value for (value, _) in values]
        self.current_values: list[T] = [value for value in default_values if value in keys]
        self.current_value: T = default_values[0] if len(default_values) and default_values[0] in keys else values[0][0]

        # Cursor index: take first selected item or first item otherwise.
        if len(self.current_values) > 0:
            self._selected_index = keys.index(self.current_values[0])
        else:
            self._selected_index = 0

        # Key bindings.
        kb = KeyBindings()

        @kb.add("up")
        def _up(event: E) -> None:
            self._selected_index = max(0, self._selected_index - 1)

        @kb.add("down")
        def _down(event: E) -> None:
            self._selected_index = min(len(self.values) - 1, self._selected_index + 1)

        @kb.add("pageup")
        def _pageup(event: E) -> None:
            w = event.app.layout.current_window
            if w.render_info:
                self._selected_index = max(0, self._selected_index - len(w.render_info.displayed_lines))

        @kb.add("pagedown")
        def _pagedown(event: E) -> None:
            w = event.app.layout.current_window
            if w.render_info:
                self._selected_index = min(
                    len(self.values) - 1,
                    self._selected_index + len(w.render_info.displayed_lines),
                )

        @kb.add("enter")
        @kb.add(" ")
        def _click(event: E) -> None:
            self._handle_enter()

        @kb.add(Keys.Any)
        def _find(event: E) -> None:
            # We first check values after the selected value, then all values.
            values = list(self.values)
            for value in values[self._selected_index + 1 :] + values:
                text = fragment_list_to_text(to_formatted_text(value[1])).lower()

                if text.startswith(event.data.lower()):
                    self._selected_index = self.values.index(value)
                    return

        # Control and window.
        self.control = FormattedTextControl(self._get_text_fragments, key_bindings=kb, focusable=True)

        self.window = Window(
            content=self.control,
            style=self.container_style,
            right_margins=[
                ConditionalMargin(
                    margin=ScrollbarMargin(display_arrows=True),
                    filter=Condition(lambda: self.show_scrollbar),
                ),
            ],
            dont_extend_height=True,
        )

    def _handle_enter(self) -> None:
        val = self.values[self._selected_index][0]
        if val in self.current_values:
            self.current_values.remove(val)
        else:
            self.current_values.append(val)

    def _get_text_fragments(self) -> StyleAndTextTuples:
        def mouse_handler(mouse_event: MouseEvent) -> None:
            """
            Set `_selected_index` and `current_value` according to the y
            position of the mouse click event.
            """
            if mouse_event.event_type == MouseEventType.MOUSE_UP:
                self._selected_index = mouse_event.position.y
                self._handle_enter()

        result: StyleAndTextTuples = []
        for i, value in enumerate(self.values):
            checked = value[0] in self.current_values
            selected = i == self._selected_index

            style = ""
            if checked:
                style += " " + self.checked_style
            if selected:
                style += " " + self.selected_style

            result.append((style, self.open_character))

            if selected:
                result.append(("[SetCursorPosition]", ""))

            if checked:
                result.append((style, "*"))
            else:
                result.append((style, " "))

            result.append((style, self.close_character))
            result.append((self.default_style, " "))
            result.extend(to_formatted_text(value[1], style=self.default_style))
            result.append(("", "\n"))

        # Add mouse handler to all fragments.
        for i in range(len(result)):
            result[i] = (result[i][0], result[i][1], mouse_handler)

        result.pop()  # Remove last newline.
        return result

    def __pt_container__(self) -> Container:
        return self.window


def create_app(
    *,
    values: Sequence[tuple[T, AnyFormattedText]],
    default_values: Sequence[T] | None = None,
    style: BaseStyle | None = None,
) -> Application[Any]:
    cb_list = MyChecklist(values=values, default_values=default_values)

    def ok_handler() -> None:
        get_app().exit(result=cb_list.current_values)

    # Key bindings.
    bindings = KeyBindings()
    bindings.add("tab")(focus_next)
    bindings.add("s-tab")(focus_previous)

    bindings.add("c-c")(lambda event: event.app.exit(result=None))
    bindings.add("c-d")(lambda event: ok_handler())

    instruction_text = "arrow keys to move; space to toggle; ctrl-c to quit; ctrl-d to finish and continue"
    instruction_label = Label(text=instruction_text)

    root_container = HSplit([instruction_label, cb_list])

    return Application(
        layout=Layout(root_container),
        key_bindings=merge_key_bindings([load_key_bindings(), bindings]),
        mouse_support=True,
        style=style,
        # full_screen=True,
    )


checked_things: list[str] | None = create_app(
    values=[
        ("eggs", "Eggs"),
        ("bacon", HTML("<blue>Bacon</blue>")),
        ("croissants", "20 Croissants"),
        ("daily", "The breakfast of the day"),
    ],
    style=Style.from_dict(
        {
            "dialog": "bg:#cdbbb3",
            "button": "bg:#bf99a4",
            "checkbox": "#e8612c",
            "dialog.body": "bg:#a9cfd0",
            "dialog shadow": "bg:#c98982",
            "frame.label": "#fcaca3",
            "dialog.body label": "#fd8bb6",
        }
    ),
).run()

if checked_things is None:
    print("Cancelled.")
else:
    print(f"Got {checked_things=}")
