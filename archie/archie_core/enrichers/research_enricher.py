"""
Research Enricher - Parse and analyze academic papers, research documents, and technical content
"""
import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """A parsed citation"""
    authors: List[str] = None
    title: str = ""
    journal: Optional[str] = None
    year: Optional[int] = None
    volume: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    citation_style: Optional[str] = None
    confidence: float = 0.0
    
    def __post_init__(self):
        if self.authors is None:
            self.authors = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'authors': self.authors,
            'title': self.title,
            'journal': self.journal,
            'year': self.year,
            'volume': self.volume,
            'pages': self.pages,
            'doi': self.doi,
            'url': self.url,
            'citation_style': self.citation_style,
            'confidence': self.confidence
        }


@dataclass
class ResearchPaper:
    """A parsed research paper"""
    title: str = ""
    authors: List[str] = None
    abstract: str = ""
    keywords: List[str] = None
    doi: Optional[str] = None
    journal: Optional[str] = None
    publication_year: Optional[int] = None
    citations: List[Citation] = None
    sections: Dict[str, str] = None
    methodology: str = ""
    results: str = ""
    conclusion: str = ""
    references_count: int = 0
    figures_count: int = 0
    tables_count: int = 0
    equations_count: int = 0
    field_of_study: Optional[str] = None
    research_type: Optional[str] = None  # experimental, theoretical, review, survey
    confidence: float = 0.0
    
    def __post_init__(self):
        if self.authors is None:
            self.authors = []
        if self.keywords is None:
            self.keywords = []
        if self.citations is None:
            self.citations = []
        if self.sections is None:
            self.sections = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'title': self.title,
            'authors': self.authors,
            'abstract': self.abstract,
            'keywords': self.keywords,
            'doi': self.doi,
            'journal': self.journal,
            'publication_year': self.publication_year,
            'citations': [c.to_dict() for c in self.citations],
            'sections': self.sections,
            'methodology': self.methodology,
            'results': self.results,
            'conclusion': self.conclusion,
            'references_count': self.references_count,
            'figures_count': self.figures_count,
            'tables_count': self.tables_count,
            'equations_count': self.equations_count,
            'field_of_study': self.field_of_study,
            'research_type': self.research_type,
            'confidence': self.confidence
        }


class ResearchEnricher:
    """Analyzes and enriches academic papers and research documents"""
    
    def __init__(self):
        # Patterns for extracting research paper elements
        self.patterns = {
            # Title patterns
            'title_tagged': re.compile(r'<title>(.*?)</title>', re.IGNORECASE | re.DOTALL),
            'title_caps': re.compile(r'^([A-Z][^a-z]*[A-Z][^a-z]*[A-Z].*?)(?:\n|$)', re.MULTILINE),
            
            # Author patterns
            'authors_simple': re.compile(r'^(?:Authors?|By):?\s*(.+?)(?:\n|$)', re.IGNORECASE | re.MULTILINE),
            'authors_email': re.compile(r'([A-Za-z\s.,-]+?)(?:\s*[,;]?\s*[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', re.MULTILINE),
            'author_names': re.compile(r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)+)'),
            
            # Abstract patterns
            'abstract_tagged': re.compile(r'<abstract>(.*?)</abstract>', re.IGNORECASE | re.DOTALL),
            'abstract_section': re.compile(r'^(?:Abstract|Summary)[:\s]*\n(.*?)(?=\n\s*(?:Keywords?|Introduction|1\.|I\.|$))', re.IGNORECASE | re.MULTILINE | re.DOTALL),
            
            # Keywords patterns
            'keywords_tagged': re.compile(r'<keywords?>(.*?)</keywords?>', re.IGNORECASE | re.DOTALL),
            'keywords_section': re.compile(r'^(?:Keywords?|Index terms?)[:\s]*(.+?)(?=\n|$)', re.IGNORECASE | re.MULTILINE),
            
            # DOI patterns
            'doi': re.compile(r'(?:doi|DOI)[:\s]*(?:https?://(?:dx\.)?doi\.org/)?([0-9]{2}\.[0-9]{4}/[-._;()/:\w\[\]]+)', re.IGNORECASE),
            
            # Journal patterns
            'journal_simple': re.compile(r'(?:Published in|Journal|Proceedings of)[:\s]*(.+?)(?=\n|,|\d{4}|Vol)', re.IGNORECASE),
            
            # Year patterns
            'year': re.compile(r'\b(19|20)\d{2}\b'),
            
            # Citation patterns (various styles)
            'citation_apa': re.compile(r'([A-Za-z\s.,&-]+?)\s*\((\d{4})\)\.\s*(.*?)\.\s*([^.]+)\.?(?:\s*doi:([^\s]+))?', re.MULTILINE),
            'citation_numbered': re.compile(r'\[(\d+)\]\s*([A-Za-z\s.,&-]+?),?\s*["""\'](.*?)["""\']\s*,?\s*([^,\n]+),?\s*(\d{4})', re.MULTILINE),
            'citation_author_year': re.compile(r'([A-Z][a-z]+(?:\s+[A-Z]\.?)*(?:\s+and\s+[A-Z][a-z]+(?:\s+[A-Z]\.?)*)*)\s*\((\d{4})\)'),
            
            # Section headers
            'section_headers': re.compile(r'^(?:\d+\.?\s*)?([A-Z][A-Za-z\s]+)(?:\n|$)', re.MULTILINE),
            'numbered_sections': re.compile(r'^(\d+(?:\.\d+)*)\s+([A-Z][A-Za-z\s]+)', re.MULTILINE),
            
            # Figures and tables
            'figures': re.compile(r'(?:Figure|Fig\.?)\s*(\d+)', re.IGNORECASE),
            'tables': re.compile(r'Table\s*(\d+)', re.IGNORECASE),
            'equations': re.compile(r'(?:Equation|Eq\.?)\s*(?:\()?(\d+)(?:\))?', re.IGNORECASE),
            
            # References section
            'references_section': re.compile(r'^(?:References|Bibliography|Literature Cited)[:\s]*\n(.*?)(?=\n\s*(?:Appendix|$))', re.IGNORECASE | re.MULTILINE | re.DOTALL),
        }
        
        # Academic field classification based on keywords
        self.field_keywords = {
            'computer_science': ['algorithm', 'software', 'computing', 'programming', 'machine learning', 'artificial intelligence', 'neural network', 'database', 'computer vision', 'natural language processing'],
            'biology': ['gene', 'protein', 'cell', 'organism', 'evolution', 'DNA', 'RNA', 'molecular', 'genetic', 'biochemistry', 'ecology', 'species'],
            'physics': ['quantum', 'particle', 'energy', 'momentum', 'wave', 'field', 'relativity', 'thermodynamics', 'mechanics', 'electromagnetic'],
            'chemistry': ['molecule', 'atom', 'reaction', 'compound', 'catalyst', 'synthesis', 'organic', 'inorganic', 'analytical', 'physical chemistry'],
            'mathematics': ['theorem', 'proof', 'equation', 'function', 'algebra', 'calculus', 'geometry', 'statistics', 'probability', 'optimization'],
            'medicine': ['patient', 'treatment', 'therapy', 'clinical', 'medical', 'diagnosis', 'disease', 'drug', 'pharmaceutical', 'health'],
            'engineering': ['design', 'system', 'control', 'optimization', 'manufacturing', 'materials', 'structural', 'mechanical', 'electrical', 'civil'],
            'psychology': ['behavior', 'cognitive', 'psychological', 'mental', 'brain', 'perception', 'learning', 'memory', 'emotion', 'social'],
            'economics': ['market', 'economic', 'financial', 'monetary', 'trade', 'investment', 'policy', 'growth', 'inflation', 'employment'],
            'social_science': ['social', 'society', 'culture', 'political', 'anthropology', 'sociology', 'demographic', 'survey', 'interview', 'qualitative']
        }
        
        # Research types based on content patterns
        self.research_type_patterns = {
            'experimental': ['experiment', 'experimental design', 'control group', 'treatment', 'hypothesis testing', 'p-value', 'statistical significance'],
            'theoretical': ['theoretical', 'mathematical model', 'theorem', 'proof', 'analytical', 'derivation', 'mathematical framework'],
            'review': ['systematic review', 'literature review', 'meta-analysis', 'survey', 'comprehensive review', 'state of the art'],
            'survey': ['questionnaire', 'survey', 'respondents', 'interview', 'qualitative study', 'ethnographic', 'case study'],
            'simulation': ['simulation', 'model', 'computational', 'numerical', 'monte carlo', 'modeling', 'simulated']
        }
        
        logger.info("🔬 Research enricher initialized")
    
    async def extract_citations(self, text: str, source_path: Optional[str] = None) -> Tuple[List[Citation], ResearchPaper]:
        """Extract citations and parse research paper from text"""
        
        if not text or not text.strip():
            return [], ResearchPaper()
        
        paper = ResearchPaper()
        citations = []
        
        # Extract paper metadata
        paper.title = self._extract_title(text)
        paper.authors = self._extract_authors(text)
        paper.abstract = self._extract_abstract(text)
        paper.keywords = self._extract_keywords(text)
        paper.doi = self._extract_doi(text)
        paper.journal = self._extract_journal(text)
        paper.publication_year = self._extract_year(text)
        
        # Extract content sections
        paper.sections = self._extract_sections(text)
        paper.methodology = self._extract_methodology(text, paper.sections)
        paper.results = self._extract_results(text, paper.sections)
        paper.conclusion = self._extract_conclusion(text, paper.sections)
        
        # Count elements
        paper.figures_count = len(self.patterns['figures'].findall(text))
        paper.tables_count = len(self.patterns['tables'].findall(text))
        paper.equations_count = len(self.patterns['equations'].findall(text))
        
        # Extract citations
        citations = self._extract_citations(text)
        paper.citations = citations
        paper.references_count = len(citations)
        
        # Classify research
        paper.field_of_study = self._classify_field(text, paper.keywords)
        paper.research_type = self._classify_research_type(text)
        
        # Calculate confidence
        paper.confidence = self._calculate_confidence(paper)
        
        logger.info(f"Parsed research paper: '{paper.title[:50]}...' ({len(citations)} citations)")
        
        return citations, paper
    
    def _extract_title(self, text: str) -> str:
        """Extract paper title"""
        
        # Try tagged title first
        tagged_match = self.patterns['title_tagged'].search(text)
        if tagged_match:
            return tagged_match.group(1).strip()
        
        # Try all-caps title pattern
        caps_match = self.patterns['title_caps'].search(text)
        if caps_match:
            title = caps_match.group(1).strip()
            if len(title) > 10 and len(title) < 200:
                return title
        
        # Fallback - use first line if it looks like a title
        lines = text.split('\n')
        for line in lines[:3]:
            line = line.strip()
            if line and len(line) > 10 and len(line) < 200:
                # Check if it doesn't start with common non-title patterns
                if not re.match(r'^(?:Abstract|Author|Keywords?|Introduction|1\.)', line, re.IGNORECASE):
                    return line
        
        return "Untitled Research Paper"
    
    def _extract_authors(self, text: str) -> List[str]:
        """Extract paper authors"""
        
        authors = []
        
        # Try simple author pattern
        simple_match = self.patterns['authors_simple'].search(text)
        if simple_match:
            author_text = simple_match.group(1).strip()
            # Split by common separators
            for sep in [',', ';', ' and ', ' & ']:
                if sep in author_text:
                    authors = [a.strip() for a in author_text.split(sep) if a.strip()]
                    break
            else:
                authors = [author_text]
        
        # Try email pattern (authors often have emails)
        if not authors:
            email_matches = self.patterns['authors_email'].findall(text)
            authors = [match.strip() for match in email_matches]
        
        # Try name pattern extraction
        if not authors:
            name_matches = self.patterns['author_names'].findall(text[:1000])  # Check first 1000 chars
            # Filter to likely author names (not too common words)
            potential_authors = []
            for name in name_matches:
                if len(name.split()) >= 2 and not name.lower() in ['the paper', 'this work', 'our results']:
                    potential_authors.append(name)
            
            # Take first few unique names
            seen = set()
            for name in potential_authors:
                if name.lower() not in seen:
                    seen.add(name.lower())
                    authors.append(name)
                    if len(authors) >= 5:  # Limit to reasonable number
                        break
        
        return authors[:10]  # Limit to 10 authors max
    
    def _extract_abstract(self, text: str) -> str:
        """Extract paper abstract"""
        
        # Try tagged abstract
        tagged_match = self.patterns['abstract_tagged'].search(text)
        if tagged_match:
            return tagged_match.group(1).strip()
        
        # Try section-based abstract
        section_match = self.patterns['abstract_section'].search(text)
        if section_match:
            abstract = section_match.group(1).strip()
            # Clean up the abstract
            abstract = re.sub(r'\s+', ' ', abstract)
            return abstract
        
        return ""
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract paper keywords"""
        
        keywords = []
        
        # Try tagged keywords
        tagged_match = self.patterns['keywords_tagged'].search(text)
        if tagged_match:
            keywords_text = tagged_match.group(1).strip()
        else:
            # Try section-based keywords
            section_match = self.patterns['keywords_section'].search(text)
            if section_match:
                keywords_text = section_match.group(1).strip()
            else:
                return []
        
        # Parse keywords
        keywords_text = re.sub(r'[;,]', ',', keywords_text)  # Normalize separators
        keywords = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]
        
        return keywords[:20]  # Limit to 20 keywords
    
    def _extract_doi(self, text: str) -> Optional[str]:
        """Extract DOI"""
        
        doi_match = self.patterns['doi'].search(text)
        if doi_match:
            return doi_match.group(1)
        return None
    
    def _extract_journal(self, text: str) -> Optional[str]:
        """Extract journal name"""
        
        journal_match = self.patterns['journal_simple'].search(text)
        if journal_match:
            return journal_match.group(1).strip()
        return None
    
    def _extract_year(self, text: str) -> Optional[int]:
        """Extract publication year"""
        
        # Look for years in first 500 characters (likely to be publication info)
        year_matches = self.patterns['year'].findall(text[:500])
        
        if year_matches:
            # Return the most recent reasonable year
            years = [int(match) for match in year_matches]
            current_year = datetime.now().year
            valid_years = [y for y in years if 1950 <= y <= current_year + 1]
            if valid_years:
                return max(valid_years)
        
        return None
    
    def _extract_sections(self, text: str) -> Dict[str, str]:
        """Extract paper sections"""
        
        sections = {}
        
        # Find section headers
        header_matches = list(self.patterns['section_headers'].finditer(text))
        numbered_matches = list(self.patterns['numbered_sections'].finditer(text))
        
        # Combine and sort matches
        all_matches = [(m.start(), m.group(1).strip(), m) for m in header_matches]
        all_matches.extend([(m.start(), m.group(2).strip(), m) for m in numbered_matches])
        all_matches.sort(key=lambda x: x[0])
        
        # Extract content between sections
        for i, (start_pos, section_name, match) in enumerate(all_matches):
            # Get next section position or end of text
            if i + 1 < len(all_matches):
                end_pos = all_matches[i + 1][0]
            else:
                end_pos = len(text)
            
            # Extract section content
            section_start = match.end()
            section_content = text[section_start:end_pos].strip()
            
            # Clean section name
            section_name = section_name.lower().replace(' ', '_')
            if len(section_content) > 10:  # Only store non-trivial sections
                sections[section_name] = section_content[:2000]  # Limit length
        
        return sections
    
    def _extract_methodology(self, text: str, sections: Dict[str, str]) -> str:
        """Extract methodology section"""
        
        # Look for common methodology section names
        method_names = ['methodology', 'methods', 'approach', 'experimental_setup', 'procedure']
        
        for name in method_names:
            if name in sections:
                return sections[name]
        
        # Fallback - search for methodology content
        method_pattern = re.compile(r'(?:methodology|methods?|approach|procedure)[:\s]*(.*?)(?=\n\s*(?:[A-Z][a-z]+|$))', re.IGNORECASE | re.DOTALL)
        match = method_pattern.search(text)
        if match:
            return match.group(1).strip()[:1000]
        
        return ""
    
    def _extract_results(self, text: str, sections: Dict[str, str]) -> str:
        """Extract results section"""
        
        # Look for results section names
        result_names = ['results', 'findings', 'experiments', 'evaluation', 'analysis']
        
        for name in result_names:
            if name in sections:
                return sections[name]
        
        return ""
    
    def _extract_conclusion(self, text: str, sections: Dict[str, str]) -> str:
        """Extract conclusion section"""
        
        # Look for conclusion section names
        conclusion_names = ['conclusion', 'conclusions', 'summary', 'discussion', 'future_work']
        
        for name in conclusion_names:
            if name in sections:
                return sections[name]
        
        return ""
    
    def _extract_citations(self, text: str) -> List[Citation]:
        """Extract citations from references section"""
        
        citations = []
        
        # Find references section
        refs_match = self.patterns['references_section'].search(text)
        if not refs_match:
            return citations
        
        refs_text = refs_match.group(1)
        
        # Try APA style citations
        apa_matches = self.patterns['citation_apa'].findall(refs_text)
        for match in apa_matches:
            authors_str, year, title, journal_info, doi = match
            citation = Citation()
            citation.authors = [a.strip() for a in re.split(r'[,&]|and', authors_str) if a.strip()]
            citation.year = int(year) if year.isdigit() else None
            citation.title = title.strip()
            citation.journal = journal_info.strip()
            citation.doi = doi if doi else None
            citation.citation_style = 'apa'
            citation.confidence = 0.8
            citations.append(citation)
        
        # Try numbered citations
        if not citations:
            numbered_matches = self.patterns['citation_numbered'].findall(refs_text)
            for match in numbered_matches:
                ref_num, authors_str, title, journal_info, year = match
                citation = Citation()
                citation.authors = [a.strip() for a in re.split(r'[,&]|and', authors_str) if a.strip()]
                citation.year = int(year) if year.isdigit() else None
                citation.title = title.strip()
                citation.journal = journal_info.strip()
                citation.citation_style = 'numbered'
                citation.confidence = 0.7
                citations.append(citation)
        
        # Limit citations
        return citations[:50]
    
    def _classify_field(self, text: str, keywords: List[str]) -> str:
        """Classify research field based on content"""
        
        text_lower = text.lower()
        field_scores = {}
        
        # Score based on field keywords
        for field, field_keywords in self.field_keywords.items():
            score = 0
            for keyword in field_keywords:
                score += text_lower.count(keyword.lower())
            
            # Bonus for keywords in the keyword list
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if any(fk.lower() in keyword_lower for fk in field_keywords):
                    score += 2
            
            if score > 0:
                field_scores[field] = score
        
        if field_scores:
            return max(field_scores, key=field_scores.get)
        
        return 'general'
    
    def _classify_research_type(self, text: str) -> str:
        """Classify research type"""
        
        text_lower = text.lower()
        
        for research_type, patterns in self.research_type_patterns.items():
            matches = sum(1 for pattern in patterns if pattern.lower() in text_lower)
            if matches >= 2:  # Require at least 2 pattern matches
                return research_type
        
        return 'general'
    
    def _calculate_confidence(self, paper: ResearchPaper) -> float:
        """Calculate confidence based on extracted metadata quality"""
        
        score = 0.0
        
        # Title quality
        if paper.title and len(paper.title) > 10:
            score += 0.15
        
        # Authors
        if paper.authors:
            score += 0.1
            if len(paper.authors) > 1:
                score += 0.05
        
        # Abstract
        if paper.abstract and len(paper.abstract) > 50:
            score += 0.15
        
        # Keywords
        if paper.keywords:
            score += 0.1
        
        # Publication info
        if paper.doi:
            score += 0.1
        if paper.journal:
            score += 0.05
        if paper.publication_year:
            score += 0.05
        
        # Content structure
        if len(paper.sections) >= 3:
            score += 0.1
        if paper.methodology:
            score += 0.05
        if paper.results:
            score += 0.05
        if paper.conclusion:
            score += 0.05
        
        # Citations
        if paper.references_count > 10:
            score += 0.1
        
        # Figures/tables
        if paper.figures_count > 0:
            score += 0.02
        if paper.tables_count > 0:
            score += 0.02
        
        return min(1.0, score)
    
    async def create_research_entity(self, paper: ResearchPaper, source_path: Optional[str] = None) -> Dict[str, Any]:
        """Create a research entity from parsed paper"""
        
        research_id = f"research_{hash(paper.title)}_{int(datetime.now().timestamp())}"
        
        research_entity = {
            'id': research_id,
            'title': paper.title or "Untitled Research",
            'authors': paper.authors,
            'abstract': paper.abstract,
            'keywords': paper.keywords,
            'doi': paper.doi,
            'journal': paper.journal,
            'publication_year': paper.publication_year,
            'field_of_study': paper.field_of_study,
            'research_type': paper.research_type,
            'methodology': paper.methodology,
            'results': paper.results,
            'conclusion': paper.conclusion,
            'references_count': paper.references_count,
            'figures_count': paper.figures_count,
            'tables_count': paper.tables_count,
            'equations_count': paper.equations_count,
            'source_path': source_path or '',
            'confidence_score': paper.confidence,
            'created': datetime.now(),
            'updated': datetime.now()
        }
        
        return research_entity
    
    def get_analysis_stats(self) -> Dict[str, Any]:
        """Get enricher statistics"""
        return {
            'supported_fields': list(self.field_keywords.keys()),
            'research_types': list(self.research_type_patterns.keys()),
            'patterns_count': len(self.patterns),
            'last_analysis': datetime.now().isoformat()
        }


# Global enricher instance
_research_enricher: Optional[ResearchEnricher] = None


def get_research_enricher() -> ResearchEnricher:
    """Get or create research enricher instance"""
    global _research_enricher
    if _research_enricher is None:
        _research_enricher = ResearchEnricher()
    return _research_enricher


async def extract_citations(text: str, source_path: Optional[str] = None) -> Tuple[List[Citation], ResearchPaper]:
    """Convenience function to extract citations from text"""
    enricher = get_research_enricher()
    return await enricher.extract_citations(text, source_path)