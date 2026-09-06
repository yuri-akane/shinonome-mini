from ui.mini import MiniRenderer
from ui.tiny import TinyRenderer

def get_renderer(display_mode: str, mode: str, judgement_y_config: int):
    """Factory function returning renderer instance based on display_mode.
    
    Parameters:
        display_mode (str): 'mini', 'tiny', 'none', or 'soundonly'
        mode (str): Game chart mode (e.g. '7K', '14K')
        judgement_y_config (int): Configured Y position for judgement line
    """
    mode_str = display_mode.lower().strip() if display_mode else 'mini'
    if mode_str in ('none', 'soundonly'):
        return None
    elif mode_str == 'tiny':
        return TinyRenderer(mode=mode, judgement_y_config=7)
    else:  # 'mini' or default
        return MiniRenderer(mode=mode, judgement_y_config=judgement_y_config)
