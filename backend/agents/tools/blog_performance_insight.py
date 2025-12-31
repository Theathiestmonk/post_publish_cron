"""
BLOG PERFORMANCE INSIGHT TOOL

Provides LIVE PERFORMANCE & SEO HEALTH INSIGHTS using Google PageSpeed Insights API.
REUSES the logic from website_analyzer_agent.py.
"""

import os
import logging
import aiohttp
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class BlogPerformanceInsight:
    def __init__(self):
        self.pagespeed_api_key = os.getenv("GOOGLE_PAGESPEED_API_KEY")
        if not self.pagespeed_api_key:
            logger.warning("GOOGLE_PAGESPEED_API_KEY not found. PageSpeed analysis will be limited.")

    async def get_live_insight(self, url: str) -> Dict[str, Any]:
        """
        Fetch LIVE performance metrics from PageSpeed Insights API.
        """
        if not self.pagespeed_api_key:
            return {"error": "PageSpeed API key not configured."}

        try:
            logger.info(f"Fetching live blog insight for: {url}")
            pagespeed_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
            params = {
                'url': url,
                'key': self.pagespeed_api_key,
                'strategy': 'mobile',
                'category': ['performance', 'accessibility', 'best-practices', 'seo']
            }

            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(pagespeed_url, params=params, timeout=60) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_psi_data(data)
                    else:
                        error_text = await response.text()
                        logger.error(f"PSI API Error: {response.status} - {error_text}")
                        return {"error": f"API returned status {response.status}"}
        except Exception as e:
            logger.error(f"Error fetching live blog insight: {str(e)}")
            return {"error": str(e)}

    def _parse_psi_data(self, data: Dict) -> Dict[str, Any]:
        """
        Parse PSI data, reusing the same logic as website_analyzer_agent.
        """
        try:
            lighthouse_result = data.get('lighthouseResult', {})
            categories = lighthouse_result.get('categories', {})
            audits = lighthouse_result.get('audits', {})

            # 1. Scores
            scores = {
                'performance': int(categories.get('performance', {}).get('score', 0) * 100),
                'seo': int(categories.get('seo', {}).get('score', 0) * 100),
                'accessibility': int(categories.get('accessibility', {}).get('score', 0) * 100),
                'best_practices': int(categories.get('best-practices', {}).get('score', 0) * 100)
            }

            # 2. Core Web Vitals
            cwv = {}
            if 'largest-contentful-paint' in audits:
                lcp = audits['largest-contentful-paint']
                cwv['lcp'] = {
                    'displayValue': lcp.get('displayValue', 'N/A'),
                    'score': int(lcp.get('score', 0) * 100)
                }
            if 'cumulative-layout-shift' in audits:
                cls = audits['cumulative-layout-shift']
                cwv['cls'] = {
                    'displayValue': cls.get('displayValue', 'N/A'),
                    'score': int(cls.get('score', 0) * 100)
                }
            # INP (using experimental or fallback if needed, but lighthouse usually has it)
            if 'interaction-to-next-paint' in audits:
                inp = audits['interaction-to-next-paint']
                cwv['inp'] = {
                    'displayValue': inp.get('displayValue', 'N/A'),
                    'score': int(inp.get('score', 0) * 100)
                }

            # 3. Opportunities (Actionable Fixes)
            opportunities = []
            for audit_id, audit in audits.items():
                if audit.get('details', {}).get('type') == 'opportunity' and audit.get('score', 1.0) < 0.9:
                    opportunities.append({
                        'title': audit.get('title'),
                        'description': audit.get('description'),
                        'impact': audit.get('score')
                    })

            return {
                "type": "blog_insight",
                "scores": scores,
                "core_web_vitals": cwv,
                "opportunities": opportunities[:5],
                "confidence": "LIVE_SNAPSHOT"
            }
        except Exception as e:
            logger.error(f"Error parsing PSI data: {str(e)}")
            return {"error": "Failed to parse insight data."}

_instance = None
def get_blog_insight_tool():
    global _instance
    if _instance is None:
        _instance = BlogPerformanceInsight()
    return _instance
