"""Generate Hawa design assets from the pinned Monad palette."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
palette = json.loads((root / 'vendor/monad_system/colors.json').read_text())
ui = palette['Default_Colors']['General_UI_Colors']
svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><rect x="1" y="1" width="46" height="46" fill="{bg}" stroke="{border}"/><g fill="none" stroke="{ink}" stroke-linecap="square" stroke-width="2.5"><path d="M9 14c10-11 20 11 30 0M9 24c10-11 20 11 30 0M9 34c10-11 20 11 30 0"/></g></svg>'''.format(bg=ui['Background']['hex'], border=ui['Border']['hex'], ink=ui['Primary_Text']['hex'])
(root / 'site/assets/hawa.svg').write_text(svg + '\n')
