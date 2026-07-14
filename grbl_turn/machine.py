"""Machine profile: firmware capabilities and lathe conventions."""

from dataclasses import dataclass


@dataclass
class MachineProfile:
    # If True the firmware is in lathe diameter mode and X words are diameters;
    # default False: X words are radii (stock GRBL behaviour).
    x_words_are_diameter: bool = False
    # Firmware supports the G76 threading cycle; if False the threading ops
    # emit explicit G33 passes computed by the app.
    has_g76: bool = True

    def x_word(self, radius: float) -> float:
        """Convert an internal radius to the value emitted as an X word."""
        return radius * 2.0 if self.x_words_are_diameter else radius
