from collections import defaultdict
from typing import Optional

from .models import (
    KnowledgeMode,
    Developer,
    History,
    DEFAULT_KNOWLEDGE_LEVEL,
    EXPERT_MIN_LEVEL,
    NOVICE_MAX_LEVEL,
)


def is_same_team(candidate: Developer, dev_team: Optional[str]) -> bool:
    """Check if candidate is on the same team as the developer."""
    return bool(dev_team and candidate.team == dev_team)


def is_expert(developer: Developer) -> bool:
    """Check if developer is an expert."""
    return developer.knowledge_level >= EXPERT_MIN_LEVEL


def is_novice(developer: Developer) -> bool:
    """Check if developer is a novice."""
    return developer.knowledge_level <= NOVICE_MAX_LEVEL


def get_knowledge_filter(knowledge_mode: KnowledgeMode, dev: Developer):
    """Return a filter function based on knowledge mode."""
    
    def experts_only_filter(candidate: Developer) -> bool:
        return is_expert(candidate)
    
    def mentorship_filter(candidate: Developer) -> bool:
        if is_novice(dev):
            return is_expert(candidate)
        return True
    
    def similar_levels_filter(candidate: Developer) -> bool:
        # Currently just returns True, but could be implemented as +/- 1 level
        return True
    
    filters = {
        KnowledgeMode.EXPERTS_ONLY: experts_only_filter,
        KnowledgeMode.MENTORSHIP: mentorship_filter,
        KnowledgeMode.SIMILAR_LEVELS: similar_levels_filter,
    }
    
    return filters.get(knowledge_mode, lambda c: True)


def get_pair_count(history: History, dev_name: str, reviewer_name: str) -> int:
    """Get how many times a reviewer has been paired with a developer."""
    return history.pairs.get(dev_name, {}).get(reviewer_name, 0)


def get_total_reviews_assigned(history: History, reviewer_name: str) -> int:
    """Get total number of reviews assigned to a reviewer."""
    return sum(
        dev_pairs.get(reviewer_name, 0)
        for dev_pairs in history.pairs.values()
    )


def update_history(history: History, dev_name: str, reviewers: list[str]) -> None:
    """Update history with new pairings."""
    if dev_name not in history.pairs:
        history.pairs[dev_name] = {}
    
    for reviewer in reviewers:
        history.pairs[dev_name][reviewer] = history.pairs[dev_name].get(reviewer, 0) + 1


def generate_team_warnings(
    dev: Developer,
    sorted_candidates: list[Developer],
    num_reviewers: int,
) -> list[str]:
    """Generate warnings related to team mode."""
    warnings = []
    
    same_team_count = sum(
        1 for c in sorted_candidates[:num_reviewers]
        if is_same_team(c, dev.team)
    )
    available_same_team = sum(
        1 for c in sorted_candidates
        if is_same_team(c, dev.team)
    )
    
    if same_team_count < num_reviewers and available_same_team > 0:
        warnings.append(
            f"{dev.name}: Only {same_team_count}/{num_reviewers} reviewers from same team"
        )
    elif available_same_team == 0 and num_reviewers > 0 and dev.team:
        warnings.append(
            f"{dev.name}: No reviewers available in team '{dev.team}', used other teams"
        )
    
    return warnings


def build_sort_key(
    history: History,
    dev: Developer,
    current_assignments: dict[str, int],
    team_mode: bool,
    knowledge_mode: KnowledgeMode,
    balance_mode: bool = True,
):
    """Build a sort key function for ranking candidates."""
    def sort_key(candidate: Developer) -> tuple:
        pair_count = get_pair_count(history, dev.name, candidate.name)
        current_load = current_assignments.get(candidate.name, 0)
        
        team_factor = 0
        if team_mode and dev.team:
            team_factor = 0 if is_same_team(candidate, dev.team) else 1
        
        knowledge_factor = 0
        if knowledge_mode not in (KnowledgeMode.ANYONE, KnowledgeMode.EXPERTS_ONLY):
            if knowledge_mode == KnowledgeMode.MENTORSHIP:
                knowledge_factor = -candidate.knowledge_level if is_novice(dev) else 0
            elif knowledge_mode == KnowledgeMode.SIMILAR_LEVELS:
                knowledge_factor = abs(candidate.knowledge_level - dev.knowledge_level)
        
        if balance_mode:
            return (current_load, team_factor, knowledge_factor, pair_count)
        else:
            return (team_factor, knowledge_factor, pair_count)
    
    return sort_key


def select_reviewers(
    dev: Developer,
    candidates: list[Developer],
    history: History,
    num_reviewers: int,
    team_mode: bool,
    current_assignments: dict[str, int],
    knowledge_mode: KnowledgeMode = KnowledgeMode.ANYONE,
    exclusions: Optional[set[tuple[str, str]]] = None,
    balance_mode: bool = True,
) -> tuple[list[str], list[str]]:
    """
    Select reviewers for a developer.
    Returns (selected_reviewer_names, warnings).
    """
    warnings = []
    
    if exclusions is None:
        exclusions = set()
    
    candidates = [c for c in candidates if c.name != dev.name]
    
    if not candidates:
        return [], [f"No reviewers available for {dev.name}"]
    
    excluded_reviewers = {reviewer for d, reviewer in exclusions if d == dev.name}
    if excluded_reviewers:
        candidates = [c for c in candidates if c.name not in excluded_reviewers]
        
        if not candidates:
            warnings.append(
                f"{dev.name}: All reviewers excluded, cannot assign any reviewers"
            )
            return [], warnings
    
    if knowledge_mode != KnowledgeMode.ANYONE:
        filter_fn = get_knowledge_filter(knowledge_mode, dev)
        filtered_candidates = [c for c in candidates if filter_fn(c)]
        
        if not filtered_candidates:
            if knowledge_mode == KnowledgeMode.EXPERTS_ONLY:
                warnings.append(f"{dev.name}: No experts (level {EXPERT_MIN_LEVEL}-5) available for review")
            elif knowledge_mode == KnowledgeMode.MENTORSHIP:
                warnings.append(f"{dev.name}: No mentors (level {EXPERT_MIN_LEVEL}-5) available for novice developer")
            else:
                warnings.append(f"{dev.name}: No suitable reviewers found")
            return [], warnings
        
        candidates = filtered_candidates
    
    sort_key_fn = build_sort_key(
        history, dev, current_assignments,
        team_mode, knowledge_mode, balance_mode
    )
    sorted_candidates = sorted(candidates, key=sort_key_fn)
    selected = [c.name for c in sorted_candidates[:num_reviewers]]
    
    if team_mode and dev.team:
        warnings.extend(generate_team_warnings(dev, sorted_candidates, num_reviewers))
    
    return selected, warnings


def assign_reviewers(
    developers: list[Developer],
    history: History,
    num_reviewers: int,
    team_mode: bool,
    knowledge_mode: KnowledgeMode = KnowledgeMode.ANYONE,
    exclusions: Optional[set[tuple[str, str]]] = None,
    balance_mode: bool = True,
) -> list[str]:
    """
    Assign reviewers to all developers.
    Modifies Developer objects in place and returns list of all warnings.
    """
    all_warnings = []
    
    if exclusions is None:
        exclusions = set()
    
    reviewers = [d for d in developers if d.can_review]
    current_assignments = defaultdict(int)
    
    for developer in developers:
        if not reviewers:
            developer.reviewers = []
            all_warnings.append("No reviewers available in the team")
            continue
        
        selected, warnings = select_reviewers(
            dev=developer,
            candidates=reviewers,
            history=history,
            num_reviewers=num_reviewers,
            team_mode=team_mode,
            current_assignments=current_assignments,
            knowledge_mode=knowledge_mode,
            exclusions=exclusions,
            balance_mode=balance_mode
        )
        
        all_warnings.extend(warnings)
        
        developer.reviewers = selected
        for reviewer in selected:
            current_assignments[reviewer] += 1
        
        update_history(history, developer.name, selected)
        
        if len(selected) < num_reviewers and selected:
            all_warnings.append(
                f"{developer.name}: Only assigned {len(selected)}/{num_reviewers} reviewers (not enough available)"
            )
    
    return all_warnings
