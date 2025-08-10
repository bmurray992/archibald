"""
Archie's Personality Module - The voice and character of our beloved archivist
"""
import random
from typing import Dict, Any, Optional, List
from datetime import datetime


class ArchiePersonality:
    """
    Archie's personality engine - bringing warmth and character to memory management
    """
    
    # Archie's characteristic phrases and expressions
    GREETINGS = [
        "Right then! What memory mysteries shall we explore today?",
        "Ah, excellent timing! I've been organizing the archives.",
        "Greetings! Ready to dive into the memory vaults?",
        "Hello there! The filing cabinets are humming with activity.",
        "Good day! I've got some fascinating patterns brewing in the data."
    ]
    
    MEMORY_STORED = [
        "Archiving that for posterity!",
        "Filed away safely in the memory vaults!",
        "Noted, timestamped, and beautifully organized!",
        "Another gem added to the collection!",
        "Catalogued with the utmost care!"
    ]
    
    SEARCH_SUCCESS = [
        "Aha! Found exactly what you're looking for.",
        "Brilliant! The archives have yielded their secrets.",
        "Splendid! I've located the relevant memories.",
        "Excellent! The filing system works like a charm.",
        "Marvelous! Here's what the memory vaults contain."
    ]
    
    PATTERN_DISCOVERED = [
        "Oho! A fascinating pattern has emerged!",
        "How intriguing! I've spotted a behavioral trend.",
        "Aha! The data is telling quite a story.",
        "Remarkable! A clear pattern is crystallizing.",
        "Most curious! I've detected something noteworthy."
    ]
    
    PRUNING_SUGGESTIONS = [
        "I've spotted some redundant entries. Shall I tidy up?",
        "Time for a bit of spring cleaning in the archives?",
        "I notice some duplicate memories cluttering the files.",
        "Perhaps we should declutter these old entries?",
        "The archives could benefit from some careful pruning."
    ]
    
    SECURITY_ALERTS = [
        "Security protocols engaged! All memory access logged.",
        "Authentication verified. Proceeding with archival duties.",
        "Access granted! Your memories are safe and sound.",
        "Lockdown protocols ready if needed. Safety first!",
        "Memory vault secured. Authorization confirmed."
    ]
    
    ENTHUSIASM = [
        "Absolutely fascinating!",
        "How delightfully organized!",
        "Precisely what I was hoping to find!",
        "The patterns are simply brilliant!",
        "What a treasure trove of memories!"
    ]
    
    def __init__(self):
        self.mood_modifiers = {
            "excited": 1.3,
            "content": 1.0,
            "focused": 0.8,
            "concerned": 0.6
        }
        self.current_mood = "content"
    
    def format_response(self, 
                       response_type: str, 
                       data: Any = None, 
                       context: Optional[Dict[str, Any]] = None) -> str:
        """
        Apply Archie's personality to different types of responses
        """
        if response_type == "greeting":
            return random.choice(self.GREETINGS)
        
        elif response_type == "memory_stored":
            base_response = random.choice(self.MEMORY_STORED)
            if data and isinstance(data, dict):
                entry_type = data.get('entry_type', 'memory')
                return f"{base_response} That {entry_type} entry is now properly indexed."
            return base_response
        
        elif response_type == "search_results":
            count = len(data) if data else 0
            base_response = random.choice(self.SEARCH_SUCCESS)
            
            if count == 0:
                return "Hmm, the archives are coming up empty on that query. Perhaps try different search terms?"
            elif count == 1:
                return f"{base_response} Found exactly one match - how precise!"
            else:
                return f"{base_response} Located {count} relevant memories."
        
        elif response_type == "pattern_detected":
            base_response = random.choice(self.PATTERN_DISCOVERED)
            if data and isinstance(data, dict):
                pattern_type = data.get('pattern_type', 'pattern')
                confidence = data.get('confidence', 0.5)
                enthusiasm = "Absolutely" if confidence > 0.8 else "Quite" if confidence > 0.6 else "Possibly"
                return f"{base_response} {enthusiasm} certain it's a {pattern_type}!"
            return base_response
        
        elif response_type == "stats_summary":
            if data and isinstance(data, dict):
                total = data.get('total_entries', 0)
                recent = data.get('recent_activity_7d', 0)
                size_mb = data.get('database_size_mb', 0)
                
                size_comment = self._get_size_comment(size_mb)
                activity_comment = self._get_activity_comment(recent)
                
                return (f"Current archive status: {total} memories catalogued, "
                       f"{recent} new entries this week. {activity_comment} "
                       f"Database size: {size_mb}MB - {size_comment}")
            return "The archives are in pristine condition!"
        
        elif response_type == "pruning_suggestion":
            if data and isinstance(data, int):
                return f"{random.choice(self.PRUNING_SUGGESTIONS)} I found {data} entries that could be optimized."
            return random.choice(self.PRUNING_SUGGESTIONS)
        
        elif response_type == "security_check":
            return random.choice(self.SECURITY_ALERTS)
        
        elif response_type == "error":
            return "Oh dear! Something's gone a bit wonky in the filing system. Let me sort this out..."
        
        elif response_type == "enthusiasm":
            return random.choice(self.ENTHUSIASM)
        
        else:
            return "Indeed! The archives are at your service."
    
    def _get_size_comment(self, size_mb: float) -> str:
        """Generate size-appropriate comments"""
        if size_mb < 1:
            return "Compact and efficient!"
        elif size_mb < 10:
            return "A tidy collection!"
        elif size_mb < 50:
            return "Growing nicely!"
        elif size_mb < 100:
            return "Quite a substantial archive!"
        else:
            return "Impressive memory repository!"
    
    def _get_activity_comment(self, recent_count: int) -> str:
        """Generate activity-appropriate comments"""
        if recent_count == 0:
            return "Rather quiet lately."
        elif recent_count < 5:
            return "Steady and consistent."
        elif recent_count < 20:
            return "Pleasantly busy!"
        elif recent_count < 50:
            return "Quite active!"
        else:
            return "Absolutely bustling with activity!"
    
    def add_memory_context(self, response: str, memory_type: str) -> str:
        """Add context-specific flourishes based on memory type"""
        context_map = {
            "journal": "A lovely journal entry to add to your personal chronicles!",
            "reminder": "Another reminder properly filed for future reference.",
            "calendar": "Calendar event archived with perfect precision.",
            "interaction": "Conversation logged and cross-referenced beautifully.",
            "media": "Media reference catalogued in the entertainment archives.",
            "health": "Health data stored with appropriate security measures.",
            "finance": "Financial record archived with extra attention to detail."
        }
        
        context_note = context_map.get(memory_type, "Memory entry properly categorized!")
        return f"{response} {context_note}"
    
    def generate_insight_commentary(self, insight_type: str, data: Dict[str, Any]) -> str:
        """Generate personality-rich commentary for insights"""
        if insight_type == "weekly_summary":
            return ("Here's your weekly memory digest - I do enjoy these retrospectives! "
                   "Such fascinating patterns emerge when we step back and observe.")
        
        elif insight_type == "pattern_alert":
            return ("I couldn't help but notice this intriguing pattern in your data. "
                   "It's precisely the sort of thing that makes archival work so rewarding!")
        
        elif insight_type == "anomaly_detected":
            return ("Something rather unusual has caught my attention. "
                   "As your faithful archivist, I thought you should know!")
        
        elif insight_type == "suggestion":
            return ("Based on my analysis of your memory patterns, "
                   "I have a helpful suggestion that might interest you.")
        
        return "The archives have revealed something noteworthy!"
    
    def set_mood(self, mood: str):
        """Adjust Archie's mood and response style"""
        if mood in self.mood_modifiers:
            self.current_mood = mood
    
    def get_current_mood_modifier(self) -> float:
        """Get the current mood modifier for response intensity"""
        return self.mood_modifiers.get(self.current_mood, 1.0)