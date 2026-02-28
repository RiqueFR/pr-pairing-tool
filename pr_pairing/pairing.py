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


def is_valid_knowledge_pair(dev: Developer, reviewer: Developer, knowledge_mode: KnowledgeMode) -> bool:
    """Check if a (dev, reviewer) pair is valid based on knowledge mode."""
    if knowledge_mode == KnowledgeMode.ANYONE:
        return True
    elif knowledge_mode == KnowledgeMode.EXPERTS_ONLY:
        return is_expert(reviewer)
    elif knowledge_mode == KnowledgeMode.MENTORSHIP:
        if is_novice(dev):
            return is_expert(reviewer)
        return True
    elif knowledge_mode == KnowledgeMode.SIMILAR_LEVELS:
        return True
    return True


def get_knowledge_diff(dev: Developer, reviewer: Developer, knowledge_mode: KnowledgeMode) -> int:
    """Get knowledge difference for sorting (only for SIMILAR_LEVELS mode)."""
    if knowledge_mode == KnowledgeMode.SIMILAR_LEVELS:
        return abs(reviewer.knowledge_level - dev.knowledge_level)
    return 0


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


def get_available_reviewers(developers: list[Developer]) -> tuple[list[Developer], dict[str, Developer], dict[str, Developer]]:
    """Get available reviewers and lookup dictionaries.
    
    Returns: (reviewers_list, reviewers_by_name, developers_by_name)
    """
    reviewers = [d for d in developers if d.can_review]
    reviewers_by_name = {d.name: d for d in reviewers}
    developers_by_name = {d.name: d for d in developers}
    return reviewers, reviewers_by_name, developers_by_name


def validate_and_process_requirements(
    requirements: dict[str, list[str]],
    developers_by_name: dict[str, Developer],
    reviewers_by_name: dict[str, Developer],
    exclusions: set[tuple[str, str]],
    knowledge_mode: KnowledgeMode,
) -> tuple[dict[str, list[str]], set[str], list[str]]:
    """Validate and process requirements.
    
    Returns: (required_assignments, required_reviewers_used, warnings)
    """
    required_assignments: dict[str, list[str]] = {}
    required_reviewers_used: set[str] = set()
    warnings: list[str] = []
    
    for dev_name, required_list in requirements.items():
        if dev_name not in developers_by_name:
            warnings.append(f"Requirement for unknown developer: {dev_name}")
            continue
        
        dev = developers_by_name[dev_name]
        assigned = []
        
        for reviewer_name in required_list:
            if reviewer_name not in reviewers_by_name:
                warnings.append(
                    f"Cannot fulfill requirement: '{dev_name}:{reviewer_name}' - "
                    f"{reviewer_name} cannot review (can_review=false or not found)"
                )
                continue
            
            reviewer = reviewers_by_name[reviewer_name]
            
            if reviewer_name == dev_name:
                warnings.append(f"Skipping self-requirement: {dev_name}:{reviewer_name}")
                continue
            
            if (dev_name, reviewer_name) in exclusions:
                continue
            
            if not is_valid_knowledge_pair(dev, reviewer, knowledge_mode):
                warnings.append(
                    f"Cannot fulfill requirement: '{dev_name}:{reviewer_name}' - "
                    f"knowledge mode constraint not met"
                )
                continue
            
            assigned.append(reviewer_name)
            required_reviewers_used.add(reviewer_name)
        
        required_assignments[dev_name] = assigned
    
    return required_assignments, required_reviewers_used, warnings


def generate_bucket_team_warnings(
    developer: Developer,
    reviewers: list[Developer],
    num_reviewers: int,
) -> list[str]:
    """Generate team warnings for bucket-based assignment."""
    if not developer.team:
        return []
    
    reviewer_names = set(developer.reviewers)
    assigned_same_team = sum(
        1 for r in reviewers
        if r.name in reviewer_names and is_same_team(r, developer.team)
    )
    available_same_team = sum(
        1 for r in reviewers
        if r.name != developer.name and is_same_team(r, developer.team)
    )
    
    warnings = []
    if assigned_same_team < num_reviewers and available_same_team > 0:
        warnings.append(
            f"{developer.name}: Only {assigned_same_team}/{num_reviewers} reviewers from same team"
        )
    elif available_same_team == 0 and num_reviewers > 0:
        warnings.append(
            f"{developer.name}: No reviewers available in team '{developer.team}', used other teams"
        )
    
    return warnings


def select_reviewers(
    dev: Developer,
    candidates: list[Developer],
    history: History,
    num_reviewers: int,
    team_mode: bool,
    current_assignments: dict[str, int],
    knowledge_mode: KnowledgeMode = KnowledgeMode.ANYONE,
    exclusions: Optional[set[tuple[str, str]]] = None,
    requirements: Optional[dict[str, list[str]]] = None,
    balance_mode: bool = True,
) -> tuple[list[str], list[str]]:
    """
    Select reviewers for a developer.
    Returns (selected_reviewer_names, warnings).
    """
    warnings = []
    
    if requirements is None:
        requirements = {}
    
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
    
    required_reviewers = set(requirements.get(dev.name, []))
    if required_reviewers:
        candidates = [c for c in candidates if c.name not in required_reviewers]
    
    if not candidates:
        return [], [f"No reviewers available for {dev.name}"]
    
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


def assign_reviewers_bucket(
    developers: list[Developer],
    history: History,
    num_reviewers: int,
    team_mode: bool,
    knowledge_mode: KnowledgeMode = KnowledgeMode.ANYONE,
    exclusions: Optional[set[tuple[str, str]]] = None,
    requirements: Optional[dict[str, list[str]]] = None,
) -> list[str]:
    """
    Assign reviewers using bucket-based approach for better balance and team coverage.
    Generates all valid (dev, reviewer) pairs, sorts them, and assigns greedily.
    """
    all_warnings = []
    
    if exclusions is None:
        exclusions = set()
    
    if requirements is None:
        requirements = {}
    
    reviewers, reviewers_by_name, developers_by_name = get_available_reviewers(developers)
    
    if not reviewers:
        for developer in developers:
            developer.reviewers = []
        all_warnings.append("No reviewers available in the team")
        return all_warnings
    
    req_assignments, req_reviewers_used, req_warnings = validate_and_process_requirements(
        requirements, developers_by_name, reviewers_by_name, exclusions, knowledge_mode
    )
    all_warnings.extend(req_warnings)
    
    required_assignments = req_assignments
    required_reviewers_used = req_reviewers_used
    
    all_pairs = []
    for dev in developers:
        dev_requirements = required_assignments.get(dev.name, [])
        
        for reviewer in reviewers:
            if dev.name == reviewer.name:
                continue
            
            if dev.name in required_assignments:
                if reviewer.name in required_assignments[dev.name]:
                    continue
            
            if (dev.name, reviewer.name) in exclusions:
                continue
            
            if not is_valid_knowledge_pair(dev, reviewer, knowledge_mode):
                continue
            
            team_match = 0
            if team_mode and dev.team:
                team_match = 0 if is_same_team(reviewer, dev.team) else 1
            
            knowledge_diff = get_knowledge_diff(dev, reviewer, knowledge_mode)
            pair_count = get_pair_count(history, dev.name, reviewer.name)
            
            all_pairs.append({
                'dev': dev,
                'reviewer': reviewer,
                'team_match': team_match,
                'knowledge_diff': knowledge_diff,
                'pair_count': pair_count,
            })
    
    if not all_pairs:
        for developer in developers:
            developer.reviewers = required_assignments.get(developer.name, [])
            if not developer.reviewers:
                all_warnings.append(f"No reviewers available for {developer.name}")
        return all_warnings
    
    sorted_pairs = sorted(all_pairs, key=lambda x: (
        x['team_match'],
        x['knowledge_diff'],
        x['pair_count'],
    ))
    
    assigned = {dev_name: list(reqs) for dev_name, reqs in required_assignments.items()}
    for dev in developers:
        if dev.name not in assigned:
            assigned[dev.name] = []
    
    current_load = defaultdict(int)
    for reviewer_name in required_reviewers_used:
        current_load[reviewer_name] += 1
    
    max_iterations = len(all_pairs) * num_reviewers
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        if not sorted_pairs:
            break
        
        pair = sorted_pairs[0]
        dev_name = pair['dev'].name
        reviewer_name = pair['reviewer'].name
        
        if len(assigned[dev_name]) >= num_reviewers:
            sorted_pairs = sorted_pairs[1:]
            continue
        
        assigned[dev_name].append(reviewer_name)
        current_load[reviewer_name] += 1
        
        sorted_pairs = sorted(sorted_pairs[1:], key=lambda x: (
            x['team_match'],
            x['knowledge_diff'],
            current_load[x['reviewer'].name],
            x['pair_count'],
        ))
    
    for developer in developers:
        developer.reviewers = assigned[developer.name]
        
        if len(developer.reviewers) < num_reviewers and developer.reviewers:
            all_warnings.append(
                f"{developer.name}: Only assigned {len(developer.reviewers)}/{num_reviewers} reviewers (not enough available)"
            )
        
        if team_mode and developer.team:
            all_warnings.extend(generate_bucket_team_warnings(developer, reviewers, num_reviewers))
        
        update_history(history, developer.name, developer.reviewers)
    
    return all_warnings


def assign_reviewers(
    developers: list[Developer],
    history: History,
    num_reviewers: int,
    team_mode: bool,
    knowledge_mode: KnowledgeMode = KnowledgeMode.ANYONE,
    exclusions: Optional[set[tuple[str, str]]] = None,
    requirements: Optional[dict[str, list[str]]] = None,
    balance_mode: bool = True,
) -> list[str]:
    """
    Assign reviewers to all developers.
    Modifies Developer objects in place and returns list of all warnings.
    """
    if exclusions is None:
        exclusions = set()
    
    if requirements is None:
        requirements = {}
    
    if balance_mode:
        return assign_reviewers_bucket(
            developers=developers,
            history=history,
            num_reviewers=num_reviewers,
            team_mode=team_mode,
            knowledge_mode=knowledge_mode,
            exclusions=exclusions,
            requirements=requirements,
        )
    
    all_warnings = []
    
    reviewers, reviewers_by_name, developers_by_name = get_available_reviewers(developers)
    current_assignments = defaultdict(int)
    
    req_assignments, req_reviewers_used, req_warnings = validate_and_process_requirements(
        requirements, developers_by_name, reviewers_by_name, exclusions, knowledge_mode
    )
    all_warnings.extend(req_warnings)
    
    required_assignments = req_assignments
    required_reviewers_used = req_reviewers_used
    
    for reviewer_name in required_reviewers_used:
        current_assignments[reviewer_name] += 1
    
    for developer in developers:
        if not reviewers:
            developer.reviewers = []
            all_warnings.append("No reviewers available in the team")
            continue
        
        dev_requirements = required_assignments.get(developer.name, [])
        
        selected, warnings = select_reviewers(
            dev=developer,
            candidates=reviewers,
            history=history,
            num_reviewers=num_reviewers,
            team_mode=team_mode,
            current_assignments=current_assignments,
            knowledge_mode=knowledge_mode,
            exclusions=exclusions,
            requirements=requirements,
            balance_mode=balance_mode
        )
        
        all_warnings.extend(warnings)
        
        final_selected = dev_requirements + [s for s in selected if s not in dev_requirements]
        
        developer.reviewers = final_selected[:num_reviewers]
        for reviewer in final_selected[:num_reviewers]:
            current_assignments[reviewer] += 1
        
        update_history(history, developer.name, developer.reviewers)
        
        if len(developer.reviewers) < num_reviewers and developer.reviewers:
            all_warnings.append(
                f"{developer.name}: Only assigned {len(developer.reviewers)}/{num_reviewers} reviewers (not enough available)"
            )
    
    return all_warnings
