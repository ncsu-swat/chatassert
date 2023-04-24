import git


def get_parent_commit(repo_dir, commit_sha):
    """Get the parent commit of a commit.

    Args:
        repo: The git repo.
        commit: The commit.

    Returns:
        The parent commit.
    """
    # Open the repository
    repo = git.Repo(repo_dir)

    # Get the commit object for the given SHA
    commit = repo.commit(commit_sha)

    # Get the SHA of the parent commit
    parent_sha = commit.parents[0].hexsha

    print("The parent commit SHA of", commit_sha, "is", parent_sha)

    return parent_sha

def clone_repo(repo_dir, git_url):
    """Clone the repository 

    Args:
        git_url: The Git URL of the repository
        repo_dir: The directory where you want it downloaded

    Returns:
        a repo object
    """
    repo = git.Repo.clone_from(git_url, repo_dir)


def reset_repo(repo_dir,commit_sha):
    # reset the repo
    repo = git.Repo(repo_dir)

    # 1. git clean -fdx
    repo.git.clean('-xdf')

    # 2. git reset --hard
    repo.git.reset('--hard')

    # 3. git checkout $com
    repo.git.checkout(commit_sha)