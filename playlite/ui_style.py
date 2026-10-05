from pathlib import Path

CHEVRON = (Path(__file__).parent / 'assets' / 'chevron-down.svg').as_posix()
DROPDOWN_STYLE = f"""
QComboBox {{ background: #2c2d2f; border: 0; border-radius: 6px; padding: 7px 30px 7px 10px; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right;
    width: 24px; border: 0; background: transparent;
    border-top-right-radius: 6px; border-bottom-right-radius: 6px; }}
QComboBox::down-arrow {{ image: url("{CHEVRON}"); width: 14px; height: 14px; }}
QComboBox QAbstractItemView {{ background: #2c2d2f; selection-background-color: #48494b; }}
"""
