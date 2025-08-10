"""
News Enricher - Parse and analyze news articles and media content
"""
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class ParsedArticle:
    """A parsed news article"""
    title: str = ""
    author: Optional[str] = None
    publication: Optional[str] = None
    published_date: Optional[datetime] = None
    url: Optional[str] = None
    summary: str = ""
    content: str = ""
    tags: List[str] = None
    category: Optional[str] = None
    sentiment: Optional[str] = None
    entities: List[str] = None
    key_quotes: List[str] = None
    word_count: int = 0
    reading_time_minutes: int = 0
    language: str = "en"
    confidence: float = 0.0
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.entities is None:
            self.entities = []
        if self.key_quotes is None:
            self.key_quotes = []
        
        if self.content:
            self.word_count = len(self.content.split())
            self.reading_time_minutes = max(1, self.word_count // 200)  # ~200 WPM average reading speed
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'title': self.title,
            'author': self.author,
            'publication': self.publication,
            'published_date': self.published_date.isoformat() if self.published_date else None,
            'url': self.url,
            'summary': self.summary,
            'content': self.content,
            'tags': self.tags,
            'category': self.category,
            'sentiment': self.sentiment,
            'entities': self.entities,
            'key_quotes': self.key_quotes,
            'word_count': self.word_count,
            'reading_time_minutes': self.reading_time_minutes,
            'language': self.language,
            'confidence': self.confidence
        }


class NewsEnricher:
    """Analyzes and enriches news articles and media content"""
    
    def __init__(self):
        # Patterns for extracting article metadata and content
        self.patterns = {
            # Common article byline patterns
            'byline': re.compile(r'By:?\s+([A-Za-z\s.,]+?)(?:\n|\||@|,\s*(?:Staff|Reporter|Correspondent))', re.IGNORECASE),
            'author_alt': re.compile(r'Author:?\s+([A-Za-z\s.,]+?)(?:\n|\||@)', re.IGNORECASE),
            
            # Publication and date patterns
            'publication': re.compile(r'(Reuters|AP|Associated Press|CNN|BBC|Fox News|NPR|The Guardian|New York Times|Washington Post|Wall Street Journal|USA Today)', re.IGNORECASE),
            'date_published': re.compile(r'Published:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+\s+\d{1,2},\s*\d{4})', re.IGNORECASE),
            'date_updated': re.compile(r'Updated:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+\s+\d{1,2},\s*\d{4})', re.IGNORECASE),
            
            # Quote extraction
            'quotes': re.compile(r'"([^"]{20,200})"'),
            'quotes_single': re.compile(r"'([^']{20,200})'"),
            
            # Entity patterns
            'locations': re.compile(r'\b(?:New York|Los Angeles|Chicago|Houston|Philadelphia|Phoenix|San Antonio|San Diego|Dallas|San Jose|Austin|Jacksonville|Fort Worth|Columbus|Charlotte|San Francisco|Indianapolis|Seattle|Denver|Washington|Boston|El Paso|Nashville|Detroit|Oklahoma City|Portland|Las Vegas|Memphis|Louisville|Baltimore|Milwaukee|Albuquerque|Tucson|Fresno|Sacramento|Mesa|Kansas City|Atlanta|Long Beach|Colorado Springs|Raleigh|Miami|Virginia Beach|Omaha|Oakland|Minneapolis|Tulsa|Arlington|Tampa|New Orleans|Wichita|Cleveland|Bakersfield|Aurora|Anaheim|Honolulu|Santa Ana|Corpus Christi|Riverside|Lexington|Stockton|Toledo|St. Paul|Newark|Greensboro|Plano|Henderson|Lincoln|Buffalo|Jersey City|Chula Vista|Fort Wayne|Orlando|St. Petersburg|Chandler|Laredo|Norfolk|Durham|Madison|Lubbock|Irvine|Winston-Salem|Glendale|Garland|Hialeah|Reno|Chesapeake|Gilbert|Baton Rouge|Irving|Scottsdale|North Las Vegas|Fremont|Boise|Richmond|San Bernardino|Birmingham|Spokane|Rochester|Des Moines|Modesto|Fayetteville|Tacoma|Oxnard|Fontana|Columbus|Montgomery|Moreno Valley|Shreveport|Aurora|Yonkers|Akron|Huntington Beach|Little Rock|Augusta|Amarillo|Glendale|Mobile|Grand Rapids|Salt Lake City|Tallahassee|Huntsville|Grand Prairie|Knoxville|Worcester|Newport News|Brownsville|Overland Park|Santa Clarita|Providence|Garden Grove|Chattanooga|Oceanside|Jackson|Fort Lauderdale|Santa Rosa|Rancho Cucamonga|Port St. Lucie|Tempe|Ontario|Vancouver|Cape Coral|Sioux Falls|Springfield|Peoria|Pembroke Pines|Elk Grove|Salem|Lancaster|Corona|Eugene|Palmdale|Salinas|Springfield|Pasadena|Fort Collins|Hayward|Pomona|Cary|Rockford|Alexandria|Escondido|McKinney|Kansas City|Joliet|Sunnyvale|Torrance|Bridgeport|Lakewood|Hollywood|Paterson|Naperville|Syracuse|Mesquite|Dayton|Savannah|Clarksville|Orange|Pasadena|Fullerton|Killeen|Frisco|Hampton|McAllen|Warren|Bellevue|West Valley City|Columbia|Olathe|Sterling Heights|New Haven|Miramar|Waco|Thousand Oaks|Cedar Rapids|Charleston|Sioux City|Round Rock|Fargo|Columbia|Coral Springs|Stamford|Plano|Concord|Hartford|Kent|Lafayette|Midland|Surprise|Denton|Victorville|Evansville|Santa Clara|Abilene|Athens|Vallejo|Allentown|Norman|Beaumont|Independence|Murfreesboro|Ann Arbor|Springfield|Berkeley|Peoria|Provo|El Monte|Columbia|Lansing|Fargo|Downey|Costa Mesa|Wilmington|Inglewood|Miami Gardens|Arvada|Westminster|Elgin|West Jordan|Broken Arrow|Norwalk|League City|Pembroke Pines|Boynton Beach|Daly City|Wichita Falls|Edison|South Bend|San Mateo|Harlingen|Bellingham|Lewisville|Hillsboro|College Station|Carrollton|Richardson|Berkeley|Green Bay|West Covina|Murrieta|Camden|Brockton|Clearwater|Antioch|West Palm Beach|Manchester|High Point|Pueblo|Burbank|Lowell|West Allis|Pompano Beach|Richmond|Norwalk|Temecula|Cambridge|Lynn|Carrollton|Lakeland|Fairfield|Dearborn|Palm Bay|Springfield|Rialto|El Cajon|Pearland|Renton|Davenport|Tyler|Sandy|Meridian|Gainesville|Westminster|Clovis|Torrance)\\b'),
            'organizations': re.compile(r'\b(?:FBI|CIA|NASA|FDA|CDC|WHO|UN|EU|NATO|Congress|Senate|House|Pentagon|White House|Supreme Court|Department of|Ministry of|Agency|Commission|Bureau|Institute|Foundation|Corporation|Inc|Ltd|LLC|Company|Corp)\\b'),
            'people': re.compile(r'\b(?:[A-Z][a-z]+\s+[A-Z][a-z]+)\b'),  # Simple name pattern
            
            # URL patterns
            'urls': re.compile(r'https?://[^\s<>"{}|^`[\]\\]+'),
        }
        
        # News categories based on keywords
        self.category_keywords = {
            'politics': ['election', 'vote', 'politician', 'government', 'congress', 'senate', 'policy', 'political', 'democrat', 'republican', 'campaign', 'president'],
            'business': ['economy', 'market', 'stock', 'financial', 'business', 'corporate', 'earnings', 'revenue', 'profit', 'investment', 'company', 'industry'],
            'technology': ['tech', 'software', 'hardware', 'internet', 'digital', 'AI', 'artificial intelligence', 'computer', 'smartphone', 'innovation', 'startup'],
            'health': ['health', 'medical', 'disease', 'vaccine', 'hospital', 'patient', 'treatment', 'drug', 'medicine', 'covid', 'pandemic', 'virus'],
            'science': ['research', 'study', 'scientist', 'discovery', 'experiment', 'data', 'analysis', 'university', 'academic', 'scientific'],
            'sports': ['game', 'team', 'player', 'season', 'championship', 'league', 'sport', 'match', 'tournament', 'athlete', 'coach'],
            'entertainment': ['movie', 'film', 'music', 'celebrity', 'actor', 'actress', 'entertainment', 'hollywood', 'album', 'concert', 'show'],
            'international': ['world', 'global', 'international', 'foreign', 'country', 'nation', 'embassy', 'diplomatic', 'trade', 'treaty'],
            'crime': ['police', 'arrest', 'crime', 'criminal', 'investigation', 'murder', 'theft', 'robbery', 'fraud', 'court', 'judge', 'trial'],
            'environment': ['climate', 'environment', 'green', 'pollution', 'carbon', 'renewable', 'energy', 'conservation', 'sustainability', 'global warming']
        }
        
        # Common publications for metadata extraction
        self.publications = {
            'reuters.com': 'Reuters',
            'ap.org': 'Associated Press',
            'apnews.com': 'Associated Press',
            'cnn.com': 'CNN',
            'bbc.com': 'BBC',
            'bbc.co.uk': 'BBC',
            'foxnews.com': 'Fox News',
            'npr.org': 'NPR',
            'theguardian.com': 'The Guardian',
            'nytimes.com': 'The New York Times',
            'washingtonpost.com': 'The Washington Post',
            'wsj.com': 'The Wall Street Journal',
            'usatoday.com': 'USA Today',
            'nbcnews.com': 'NBC News',
            'abcnews.go.com': 'ABC News',
            'cbsnews.com': 'CBS News',
            'time.com': 'Time',
            'newsweek.com': 'Newsweek',
            'politico.com': 'Politico',
            'bloomberg.com': 'Bloomberg'
        }
        
        logger.info("📰 News enricher initialized")
    
    async def clean_article(self, text: str, source_url: Optional[str] = None) -> ParsedArticle:
        """Clean and parse article content from raw text"""
        
        if not text or not text.strip():
            return ParsedArticle()
        
        article = ParsedArticle()
        
        # Extract basic metadata
        article.title = self._extract_title(text)
        article.author = self._extract_author(text)
        article.publication = self._extract_publication(text, source_url)
        article.published_date = self._extract_date(text)
        article.url = source_url
        
        # Clean and structure content
        cleaned_content = self._clean_content(text)
        article.content = cleaned_content
        article.summary = self._generate_summary(cleaned_content)
        
        # Extract entities and quotes
        article.key_quotes = self._extract_quotes(text)
        article.entities = self._extract_entities(text)
        
        # Analyze content
        article.tags = self._extract_tags(cleaned_content)
        article.category = self._categorize_article(cleaned_content, article.tags)
        article.sentiment = self._analyze_sentiment(cleaned_content)
        
        # Set confidence based on extracted metadata quality
        article.confidence = self._calculate_confidence(article)
        
        logger.info(f"Parsed article: '{article.title[:50]}...' ({article.word_count} words)")
        
        return article
    
    def _extract_title(self, text: str) -> str:
        """Extract article title"""
        
        lines = text.split('\n')
        
        # Look for title-like lines (usually first non-empty line)
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if line and len(line) > 10 and len(line) < 200:
                # Remove common prefixes
                for prefix in ['Title:', 'Headline:', 'Article:', 'Story:']:
                    if line.startswith(prefix):
                        line = line[len(prefix):].strip()
                
                # Check if it looks like a title (not too long, not all caps unless short)
                if len(line) < 150 and (not line.isupper() or len(line) < 50):
                    return line
        
        # Fallback - use first sentence if no clear title
        first_sentence = text.split('.')[0].strip()
        if len(first_sentence) > 10 and len(first_sentence) < 200:
            return first_sentence
        
        return "Untitled Article"
    
    def _extract_author(self, text: str) -> Optional[str]:
        """Extract article author"""
        
        # Try different byline patterns
        byline_match = self.patterns['byline'].search(text)
        if byline_match:
            author = byline_match.group(1).strip()
            # Clean up common suffixes
            author = re.sub(r',\s*(Staff Writer|Reporter|Correspondent).*', '', author)
            return author
        
        # Try alternative author pattern
        author_match = self.patterns['author_alt'].search(text)
        if author_match:
            return author_match.group(1).strip()
        
        return None
    
    def _extract_publication(self, text: str, source_url: Optional[str] = None) -> Optional[str]:
        """Extract publication name"""
        
        # Try to extract from URL first
        if source_url:
            try:
                domain = urlparse(source_url).netloc.lower()
                domain = domain.replace('www.', '')
                if domain in self.publications:
                    return self.publications[domain]
            except:
                pass
        
        # Try to find in text
        pub_match = self.patterns['publication'].search(text)
        if pub_match:
            return pub_match.group(1)
        
        return None
    
    def _extract_date(self, text: str) -> Optional[datetime]:
        """Extract publication date"""
        
        # Try published date first
        date_match = self.patterns['date_published'].search(text)
        if not date_match:
            date_match = self.patterns['date_updated'].search(text)
        
        if date_match:
            date_str = date_match.group(1)
            return self._parse_date(date_str)
        
        return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats"""
        
        if not date_str:
            return None
        
        date_str = date_str.strip()
        
        # Common date formats used in news
        formats = [
            '%B %d, %Y',    # January 1, 2024
            '%b %d, %Y',    # Jan 1, 2024
            '%m/%d/%Y',     # 1/1/2024
            '%m-%d-%Y',     # 1-1-2024
            '%Y-%m-%d',     # 2024-1-1
            '%d/%m/%Y',     # 1/1/2024 (international)
            '%d-%m-%Y',     # 1-1-2024 (international)
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        return None
    
    def _clean_content(self, text: str) -> str:
        """Clean article content from raw text"""
        
        lines = text.split('\n')
        content_lines = []
        
        skip_patterns = [
            r'^(by|author):\s*',
            r'^(published|updated):\s*',
            r'^(share|subscribe|follow)\s*',
            r'^(advertisement|ad)\s*',
            r'^(copyright|©)\s*',
            r'^(more from|related)\s*',
            r'^\s*(twitter|facebook|instagram)\s*',
            r'^(tags?|categories?)\s*:',
        ]
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Skip lines matching skip patterns
            if any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
                continue
            
            # Skip very short lines (likely metadata)
            if len(line) < 10:
                continue
            
            # Skip lines that are mostly punctuation or numbers
            if len(re.sub(r'[^a-zA-Z\s]', '', line)) < len(line) * 0.3:
                continue
            
            content_lines.append(line)
        
        # Join paragraphs
        content = ' '.join(content_lines)
        
        # Clean up excessive whitespace
        content = re.sub(r'\s+', ' ', content)
        
        return content.strip()
    
    def _generate_summary(self, content: str, max_length: int = 300) -> str:
        """Generate article summary"""
        
        if len(content) <= max_length:
            return content
        
        # Simple extractive summarization - take first few sentences
        sentences = re.split(r'[.!?]+', content)
        summary_sentences = []
        current_length = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            if current_length + len(sentence) > max_length - 10:  # Leave room for ellipsis
                break
                
            summary_sentences.append(sentence)
            current_length += len(sentence)
        
        if summary_sentences:
            summary = '. '.join(summary_sentences)
            if current_length < len(content):
                summary += "..."
            return summary
        
        # Fallback - just truncate
        return content[:max_length-3] + "..."
    
    def _extract_quotes(self, text: str) -> List[str]:
        """Extract key quotes from the article"""
        
        quotes = []
        
        # Find quoted text
        quote_matches = self.patterns['quotes'].findall(text)
        quotes.extend(quote_matches)
        
        # Also try single quotes
        single_quote_matches = self.patterns['quotes_single'].findall(text)
        quotes.extend(single_quote_matches)
        
        # Clean and deduplicate quotes
        cleaned_quotes = []
        seen = set()
        
        for quote in quotes:
            quote = quote.strip()
            if len(quote) >= 20 and len(quote) <= 200:  # Reasonable quote length
                quote_lower = quote.lower()
                if quote_lower not in seen:
                    seen.add(quote_lower)
                    cleaned_quotes.append(quote)
        
        return cleaned_quotes[:5]  # Limit to 5 key quotes
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract named entities from the text"""
        
        entities = []
        
        # Extract locations
        location_matches = self.patterns['locations'].findall(text)
        entities.extend([f"LOCATION:{loc}" for loc in location_matches])
        
        # Extract organizations
        org_matches = self.patterns['organizations'].findall(text)
        entities.extend([f"ORG:{org}" for org in org_matches])
        
        # Extract people (simple pattern)
        people_matches = self.patterns['people'].findall(text)
        entities.extend([f"PERSON:{person}" for person in people_matches if len(person.split()) == 2])
        
        # Remove duplicates and limit
        return list(set(entities))[:20]
    
    def _extract_tags(self, text: str) -> List[str]:
        """Extract relevant tags from article content"""
        
        text_lower = text.lower()
        tags = []
        
        # Extract tags based on category keywords
        for category, keywords in self.category_keywords.items():
            matches = sum(1 for keyword in keywords if keyword.lower() in text_lower)
            if matches >= 2:  # Require at least 2 keyword matches
                tags.append(category)
        
        # Add common news tags based on content analysis
        if any(word in text_lower for word in ['breaking', 'urgent', 'developing']):
            tags.append('breaking')
        
        if any(word in text_lower for word in ['analysis', 'opinion', 'editorial', 'commentary']):
            tags.append('analysis')
        
        if any(word in text_lower for word in ['exclusive', 'interview', 'investigation']):
            tags.append('exclusive')
        
        return tags
    
    def _categorize_article(self, content: str, tags: List[str]) -> str:
        """Categorize the article based on content and tags"""
        
        # Use tags if available
        if tags:
            # Count occurrences of each category
            category_scores = {}
            for tag in tags:
                if tag in self.category_keywords:
                    category_scores[tag] = category_scores.get(tag, 0) + 1
            
            if category_scores:
                return max(category_scores, key=category_scores.get)
        
        # Fallback to keyword analysis
        content_lower = content.lower()
        
        for category, keywords in self.category_keywords.items():
            score = sum(1 for keyword in keywords if keyword.lower() in content_lower)
            if score >= 3:  # Require at least 3 keyword matches
                return category
        
        return 'general'
    
    def _analyze_sentiment(self, text: str) -> str:
        """Basic sentiment analysis of the article"""
        
        # Simple rule-based sentiment analysis
        positive_words = {
            'success', 'achievement', 'victory', 'win', 'celebrate', 'progress', 'improve',
            'positive', 'good', 'great', 'excellent', 'outstanding', 'breakthrough',
            'benefit', 'advantage', 'opportunity', 'growth', 'recovery', 'rise'
        }
        
        negative_words = {
            'crisis', 'problem', 'issue', 'concern', 'worry', 'fear', 'danger', 'risk',
            'decline', 'fall', 'drop', 'failure', 'loss', 'damage', 'harm', 'threat',
            'controversy', 'scandal', 'conflict', 'violence', 'attack', 'death', 'tragedy'
        }
        
        neutral_words = {
            'report', 'announce', 'state', 'according', 'official', 'government',
            'study', 'research', 'data', 'information', 'meeting', 'conference'
        }
        
        words = re.findall(r'\b[A-Za-z]+\b', text.lower())
        
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        neutral_count = sum(1 for word in words if word in neutral_words)
        
        # Calculate sentiment based on word counts
        if neutral_count > positive_count + negative_count:
            return 'neutral'
        elif positive_count > negative_count * 1.5:  # Require stronger positive signal
            return 'positive'
        elif negative_count > positive_count * 1.5:  # Require stronger negative signal
            return 'negative'
        else:
            return 'neutral'
    
    def _calculate_confidence(self, article: ParsedArticle) -> float:
        """Calculate confidence score based on extracted metadata quality"""
        
        score = 0.0
        
        # Title quality
        if article.title and len(article.title) > 10:
            score += 0.2
        
        # Author information
        if article.author:
            score += 0.15
        
        # Publication information
        if article.publication:
            score += 0.15
        
        # Date information
        if article.published_date:
            score += 0.1
        
        # Content quality
        if article.word_count > 100:
            score += 0.2
        if article.word_count > 500:
            score += 0.1
        
        # Entity and quote extraction
        if article.entities:
            score += 0.05
        if article.key_quotes:
            score += 0.05
        
        return min(1.0, score)
    
    async def create_media_entity(self, article: ParsedArticle, source_path: Optional[str] = None) -> Dict[str, Any]:
        """Create a MediaItem entity from parsed article"""
        
        media_id = f"article_{hash(article.content)}_{int(datetime.now().timestamp())}"
        
        media_entity = {
            'id': media_id,
            'title': article.title or "Untitled Article",
            'media_type': 'article',
            'url': article.url or '',
            'file_path': source_path or '',
            'thumbnail_path': '',
            'metadata': {
                'author': article.author,
                'publication': article.publication,
                'published_date': article.published_date.isoformat() if article.published_date else None,
                'word_count': article.word_count,
                'reading_time_minutes': article.reading_time_minutes,
                'summary': article.summary,
                'entities': article.entities,
                'key_quotes': article.key_quotes,
                'sentiment': article.sentiment,
                'confidence': article.confidence
            },
            'tags': article.tags,
            'description': article.summary or article.content[:500] + "..." if len(article.content) > 500 else article.content,
            'created': datetime.now(),
            'updated': datetime.now()
        }
        
        return media_entity
    
    def get_analysis_stats(self) -> Dict[str, Any]:
        """Get enricher statistics"""
        return {
            'supported_sources': list(self.publications.keys()),
            'categories': list(self.category_keywords.keys()),
            'patterns_count': len(self.patterns),
            'last_analysis': datetime.now().isoformat()
        }


# Global enricher instance
_news_enricher: Optional[NewsEnricher] = None


def get_news_enricher() -> NewsEnricher:
    """Get or create news enricher instance"""
    global _news_enricher
    if _news_enricher is None:
        _news_enricher = NewsEnricher()
    return _news_enricher


async def clean_article(text: str, source_url: Optional[str] = None) -> ParsedArticle:
    """Convenience function to clean and parse an article"""
    enricher = get_news_enricher()
    return await enricher.clean_article(text, source_url)