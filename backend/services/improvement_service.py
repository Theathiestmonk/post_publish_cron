"""
Improvement Service - Generate AI-powered improvement suggestions

This service analyzes analytics data and generates personalized improvement suggestions
using AI/ML or rule-based recommendations.

PHASE 6: Enhanced with data-driven insights including percentages, deltas, and comparisons.
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def generate_improvements_from_data(data: Dict[str, Any], metrics: List[str]) -> Optional[Dict[str, Any]]:
    """
    PHASE 6: Generate data-driven improvement suggestions with percentages, deltas, and comparisons.
    
    Args:
        data: Analytics data dict (e.g., {"reach": 1000, "impressions": 5000, "engagement": 50})
               Can also include "period_comparison", "growth_rates", "day_wise_breakdown"
        metrics: List of metrics to generate improvements for
    
    Returns:
        Dict with improvement suggestions or None if error
    """
    try:
        if not data or not metrics:
            return None
        
        suggestions = {}
        
        # Extract comparison data if available
        period_comparison = data.get("period_comparison", {})
        growth_rates = data.get("growth_rates", {})
        
        logger.info(f"🔍 insight_generation_started: Generating insights for {len(metrics)} metrics")
        
        # Generate data-driven improvements for each metric
        for metric in metrics:
            logger.debug(f"🔍 Processing metric: {metric}")
            metric_value = data.get(metric, 0)
            
            # PHASE 6: Get comparison data for this metric
            comparison = period_comparison.get(metric, {})
            growth_rate = growth_rates.get(metric, 0)
            percent_change = comparison.get("percent_change", 0)
            trend = comparison.get("trend", "stable")
            previous_value = comparison.get("previous", 0)
            
            # Build data-driven suggestion message
            insight_parts = []
            
            if metric == "reach":
                if metric_value < 1000:
                    base_suggestion = "Your reach is below average. Try posting at peak engagement times (9 AM, 12 PM, 6 PM) and use relevant hashtags to increase visibility."
                    target = 1000
                elif metric_value < 5000:
                    base_suggestion = "Your reach is good but can be improved. Focus on creating shareable content and engaging with your audience in comments."
                    target = 5000
                else:
                    base_suggestion = "Great reach! Maintain consistency and continue engaging with your audience."
                    target = int(metric_value * 1.2)
                
                # Add data-driven insights
                if comparison:
                    if trend == "up" and percent_change > 10:
                        insight_parts.append(f"📈 Your reach increased by {percent_change:.1f}% compared to the previous period - great progress!")
                    elif trend == "down" and abs(percent_change) > 10:
                        insight_parts.append(f"📉 Your reach decreased by {abs(percent_change):.1f}% - consider posting more frequently.")
                    elif trend == "stable":
                        insight_parts.append(f"➡️ Your reach remained stable at {metric_value}.")
                
                if growth_rate != 0:
                    if growth_rate > 0:
                        insight_parts.append(f"📊 Growth rate: +{growth_rate:.1f}% over the period.")
                    else:
                        insight_parts.append(f"📊 Growth rate: {growth_rate:.1f}% - needs attention.")
                
                suggestion_text = base_suggestion
                if insight_parts:
                    suggestion_text += "\n\n" + "\n".join(insight_parts)
                
                suggestions[metric] = {
                    "current": metric_value,
                    "suggestion": suggestion_text,
                    "target": target
                }
                
                # Add comparison data if available
                if comparison:
                    suggestions[metric]["comparison"] = comparison
                if growth_rate != 0:
                    suggestions[metric]["growth_rate"] = growth_rate
            
            elif metric == "impressions":
                if metric_value < 5000:
                    base_suggestion = "Increase impressions by posting more frequently (3-5 times per week) and using trending hashtags."
                    target = 5000
                elif metric_value < 20000:
                    base_suggestion = "Good impressions! Try experimenting with different content formats (videos, carousels, reels) to boost visibility."
                    target = 20000
                else:
                    base_suggestion = "Excellent impressions! Keep up the great work and maintain your posting schedule."
                    target = int(metric_value * 1.15)
                
                insight_parts = []
                if comparison:
                    if trend == "up" and percent_change > 15:
                        insight_parts.append(f"📈 Impressions increased by {percent_change:.1f}% - your content is reaching more people!")
                    elif trend == "down" and abs(percent_change) > 15:
                        insight_parts.append(f"📉 Impressions decreased by {abs(percent_change):.1f}% - consider optimizing posting times.")
                
                if growth_rate != 0:
                    insight_parts.append(f"📊 Growth rate: {growth_rate:+.1f}%")
                
                suggestion_text = base_suggestion
                if insight_parts:
                    suggestion_text += "\n\n" + "\n".join(insight_parts)
                
                suggestions[metric] = {
                    "current": metric_value,
                    "suggestion": suggestion_text,
                    "target": target
                }
                
                if comparison:
                    suggestions[metric]["comparison"] = comparison
                if growth_rate != 0:
                    suggestions[metric]["growth_rate"] = growth_rate
            
            elif metric == "engagement":
                reach = data.get("reach", 1)
                engagement_rate = (metric_value / reach * 100) if reach > 0 else 0
                
                if engagement_rate < 1:
                    base_suggestion = "Low engagement rate. Ask questions in your captions, use call-to-actions, and respond to comments quickly to boost engagement."
                    target = int(reach * 0.02)  # Target 2% engagement rate
                elif engagement_rate < 3:
                    base_suggestion = "Decent engagement! Try posting user-generated content and running contests to increase interaction."
                    target = int(reach * 0.04)  # Target 4% engagement rate
                else:
                    base_suggestion = "Excellent engagement rate! Your audience loves your content. Keep creating valuable posts."
                    target = int(metric_value * 1.1)
                
                insight_parts = [f"📊 Current engagement rate: {engagement_rate:.2f}%"]
                
                if comparison:
                    if trend == "up" and percent_change > 5:
                        insight_parts.append(f"📈 Engagement increased by {percent_change:.1f}% - your audience is more engaged!")
                    elif trend == "down" and abs(percent_change) > 5:
                        insight_parts.append(f"📉 Engagement decreased by {abs(percent_change):.1f}% - focus on interactive content.")
                
                if growth_rate != 0:
                    insight_parts.append(f"📊 Growth rate: {growth_rate:+.1f}%")
                
                suggestion_text = base_suggestion
                if insight_parts:
                    suggestion_text += "\n\n" + "\n".join(insight_parts)
                
                suggestions[metric] = {
                    "current": metric_value,
                    "engagement_rate": f"{engagement_rate:.2f}%",
                    "suggestion": suggestion_text,
                    "target": target
                }
                
                if comparison:
                    suggestions[metric]["comparison"] = comparison
                if growth_rate != 0:
                    suggestions[metric]["growth_rate"] = growth_rate
            
            elif metric == "likes":
                if metric_value < 100:
                    base_suggestion = "Increase likes by creating visually appealing content and posting consistently at optimal times."
                    target = 100
                else:
                    base_suggestion = "Good likes! Try using more engaging visuals and asking for likes in your captions."
                    target = int(metric_value * 1.2)
                
                insight_parts = []
                if comparison:
                    if trend == "up" and percent_change > 20:
                        insight_parts.append(f"📈 Likes increased by {percent_change:.1f}% - your content resonates!")
                    elif trend == "down" and abs(percent_change) > 20:
                        insight_parts.append(f"📉 Likes decreased by {abs(percent_change):.1f}% - review your content strategy.")
                
                if growth_rate != 0:
                    insight_parts.append(f"📊 Growth rate: {growth_rate:+.1f}%")
                
                suggestion_text = base_suggestion
                if insight_parts:
                    suggestion_text += "\n\n" + "\n".join(insight_parts)
                
                suggestions[metric] = {
                    "current": metric_value,
                    "suggestion": suggestion_text,
                    "target": target
                }
                
                if comparison:
                    suggestions[metric]["comparison"] = comparison
                if growth_rate != 0:
                    suggestions[metric]["growth_rate"] = growth_rate
            
            elif metric == "comments":
                if metric_value < 10:
                    base_suggestion = "Boost comments by asking questions, sharing personal stories, and responding to every comment."
                    target = 10
                else:
                    base_suggestion = "Great comment engagement! Keep the conversation going by replying thoughtfully."
                    target = int(metric_value * 1.15)
                
                insight_parts = []
                if comparison:
                    if trend == "up" and percent_change > 25:
                        insight_parts.append(f"📈 Comments increased by {percent_change:.1f}% - great community engagement!")
                    elif trend == "down" and abs(percent_change) > 25:
                        insight_parts.append(f"📉 Comments decreased by {abs(percent_change):.1f}% - try more interactive content.")
                
                if growth_rate != 0:
                    insight_parts.append(f"📊 Growth rate: {growth_rate:+.1f}%")
                
                suggestion_text = base_suggestion
                if insight_parts:
                    suggestion_text += "\n\n" + "\n".join(insight_parts)
                
                suggestions[metric] = {
                    "current": metric_value,
                    "suggestion": suggestion_text,
                    "target": target
                }
                
                if comparison:
                    suggestions[metric]["comparison"] = comparison
                if growth_rate != 0:
                    suggestions[metric]["growth_rate"] = growth_rate
            
            elif metric == "followers":
                if metric_value < 1000:
                    suggestions[metric] = {
                        "current": metric_value,
                        "suggestion": "Grow followers by collaborating with influencers, using relevant hashtags, and creating shareable content.",
                        "target": 1000
                    }
                elif metric_value < 10000:
                    suggestions[metric] = {
                        "current": metric_value,
                        "suggestion": "Steady growth! Focus on creating value-driven content and engaging with your community.",
                        "target": 10000
                    }
                else:
                    suggestions[metric] = {
                        "current": metric_value,
                        "suggestion": "Strong follower base! Maintain authenticity and continue providing value to your audience.",
                        "target": metric_value * 1.1
                    }
            
            elif metric == "views":
                if metric_value < 1000:
                    suggestions[metric] = {
                        "current": metric_value,
                        "suggestion": "Increase video views by creating attention-grabbing thumbnails and posting during peak hours.",
                        "target": 1000
                    }
                else:
                    suggestions[metric] = {
                        "current": metric_value,
                        "suggestion": "Good views! Try creating series content and using trending sounds/music to boost visibility.",
                        "target": metric_value * 1.25
                    }
            
            else:
                # Generic suggestion for other metrics with data-driven insights
                base_suggestion = f"Focus on creating high-quality, engaging content to improve your {metric.replace('_', ' ')}."
                target = int(metric_value * 1.2)
                
                insight_parts = []
                if comparison:
                    if trend == "up":
                        insight_parts.append(f"📈 {metric.replace('_', ' ').title()} increased by {percent_change:.1f}%")
                    elif trend == "down":
                        insight_parts.append(f"📉 {metric.replace('_', ' ').title()} decreased by {abs(percent_change):.1f}%")
                
                if growth_rate != 0:
                    insight_parts.append(f"📊 Growth rate: {growth_rate:+.1f}%")
                
                suggestion_text = base_suggestion
                if insight_parts:
                    suggestion_text += "\n\n" + "\n".join(insight_parts)
                
                suggestions[metric] = {
                    "current": metric_value,
                    "suggestion": suggestion_text,
                    "target": target
                }
                
                if comparison:
                    suggestions[metric]["comparison"] = comparison
                if growth_rate != 0:
                    suggestions[metric]["growth_rate"] = growth_rate
        
        if suggestions:
            logger.info(f"✅ insight_generated_from_metrics: Generated {len(suggestions)} improvement suggestions")
            logger.debug(f"📊 insight_generated_from_metrics: Metrics processed: {list(suggestions.keys())}")
        else:
            logger.warning(f"⚠️ insight_generation_failed: No suggestions generated")
        
        return suggestions if suggestions else None
        
    except Exception as e:
        logger.error(f"❌ Error generating improvements: {e}", exc_info=True)
        return None

