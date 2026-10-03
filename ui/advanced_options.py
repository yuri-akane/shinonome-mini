from dataclasses import dataclass
from helpers.options import Options

@dataclass
class AdvancedOptionsState:
    show_result: bool = True
    display_mode: str = "mini"
    stdout_result: bool = False

    @classmethod
    def from_options(cls, opts: Options) -> "AdvancedOptionsState":
        return cls(
            show_result=opts.show_result,
            display_mode=opts.display_mode,
            stdout_result=opts.stdout_result
        )

    def apply_to_options(self, opts: Options) -> None:
        opts.show_result = self.show_result
        opts.display_mode = self.display_mode
        opts.stdout_result = self.stdout_result

    def toggle_display_mode(self) -> None:
        modes = ["mini", "tiny", "mw"]
        if self.display_mode not in modes:
            self.display_mode = "mini"
        else:
            idx = modes.index(self.display_mode)
            self.display_mode = modes[(idx + 1) % len(modes)]
