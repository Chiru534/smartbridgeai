# Exhaustive GitHub + Google Drive MCP Validation Report (2026-03-15)

- Generated at (IST): 2026-03-15T10:32:42.150456+05:30
- Backend URL: `http://localhost:8000`
- Backend user: `admin`
- Connector user: `admin`
- Write validation enabled: `True`

## Preflight
- Backend URL: `http://localhost:8000`
- Authenticated as backend user `admin`.
- Connector status:
```json
[
  {
    "server": "github",
    "configured": true,
    "command": [
      "python",
      "-m",
      "platform_core.github_mcp_server"
    ],
    "oauth_configured": true,
    "pat_configured": false,
    "service_account_configured": false,
    "auth_flow": "oauth_or_pat",
    "oauth_redirect_uri": "http://localhost:8000/api/oauth/github/callback",
    "setup_hint": "Create a GitHub OAuth app and set its callback URL to http://localhost:8000/api/oauth/github/callback. Then place the client ID and client secret in backend/.env. Alternatively, set GITHUB_PAT in backend/.env to use a shared local token without the OAuth popup.",
    "last_error": null
  },
  {
    "server": "google_drive",
    "configured": true,
    "command": [
      "python",
      "-m",
      "platform_core.google_drive_mcp_server"
    ],
    "oauth_configured": true,
    "pat_configured": false,
    "service_account_configured": false,
    "auth_flow": "oauth_popup",
    "oauth_redirect_uri": "http://localhost:8000/api/oauth/google/callback",
    "setup_hint": "A Google service-account email is configured, but no service-account key is configured. Add GOOGLE_SERVICE_ACCOUNT_JSON_PATH or GOOGLE_SERVICE_ACCOUNT_JSON in backend/.env. Until then, the app will keep using the Google OAuth popup instead of direct folder access.",
    "last_error": null
  }
]
```
- Connector accounts:
```json
[
  {
    "connector_name": "github",
    "connected": true,
    "auth_method": "oauth",
    "display_name": "Chiru534",
    "login": "Chiru534",
    "email": null,
    "created_at": "2026-03-14T10:17:59.039310",
    "updated_at": "2026-03-14T10:17:59.039379"
  },
  {
    "connector_name": "google_drive",
    "connected": true,
    "auth_method": "oauth",
    "display_name": "Chiranjeevi Madem",
    "login": "chiranjeevi4.adarsh@gmail.com",
    "email": "chiranjeevi4.adarsh@gmail.com",
    "created_at": "2026-03-14T14:09:44.247269",
    "updated_at": "2026-03-15T04:57:07.830773"
  }
]
```
- Stored connector scope summary:
| Connector | Identity | Stored Scope |
| --- | --- | --- |
| github | Chiru534 | scope unavailable from current MCP output |
| google_drive | chiranjeevi4.adarsh@gmail.com | https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email openid https://www.googleapis.com/auth/drive.metadata.readonly |

## Tool Discovery
### `github` tools (28)
- `github_get_authenticated_user`: No description provided.
```json
{
  "properties": {},
  "required": [],
  "title": "get_authenticated_userArguments",
  "type": "object"
}
```
- `github_get_token_info`: No description provided.
```json
{
  "properties": {},
  "required": [],
  "title": "get_token_infoArguments",
  "type": "object"
}
```
- `github_list_organizations`: No description provided.
```json
{
  "properties": {
    "per_page": {
      "default": 100,
      "title": "Per Page",
      "type": "integer"
    },
    "page": {
      "default": 1,
      "title": "Page",
      "type": "integer"
    }
  },
  "required": [],
  "title": "list_organizationsArguments",
  "type": "object"
}
```
- `github_list_my_repositories`: No description provided.
```json
{
  "properties": {
    "visibility": {
      "default": "all",
      "title": "Visibility",
      "type": "string"
    },
    "affiliation": {
      "default": "owner,collaborator,organization_member",
      "title": "Affiliation",
      "type": "string"
    },
    "sort": {
      "default": "updated",
      "title": "Sort",
      "type": "string"
    },
    "per_page": {
      "default": 100,
      "title": "Per Page",
      "type": "integer"
    },
    "page": {
      "default": 1,
      "title": "Page",
      "type": "integer"
    }
  },
  "required": [],
  "title": "list_my_repositoriesArguments",
  "type": "object"
}
```
- `github_list_user_repositories`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "sort": {
      "default": "updated",
      "title": "Sort",
      "type": "string"
    },
    "per_page": {
      "default": 100,
      "title": "Per Page",
      "type": "integer"
    },
    "page": {
      "default": 1,
      "title": "Page",
      "type": "integer"
    }
  },
  "required": [
    "owner"
  ],
  "title": "list_user_repositoriesArguments",
  "type": "object"
}
```
- `github_search_repositories`: No description provided.
```json
{
  "properties": {
    "query": {
      "title": "Query",
      "type": "string"
    },
    "per_page": {
      "default": 10,
      "title": "Per Page",
      "type": "integer"
    }
  },
  "required": [
    "query"
  ],
  "title": "search_repositoriesArguments",
  "type": "object"
}
```
- `github_get_repository`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    }
  },
  "required": [
    "owner",
    "repo"
  ],
  "title": "get_repositoryArguments",
  "type": "object"
}
```
- `github_list_directory`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    },
    "path": {
      "default": "",
      "title": "Path",
      "type": "string"
    },
    "ref": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Ref"
    }
  },
  "required": [
    "owner",
    "repo"
  ],
  "title": "list_directoryArguments",
  "type": "object"
}
```
- `github_get_file`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    },
    "path": {
      "title": "Path",
      "type": "string"
    },
    "ref": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Ref"
    }
  },
  "required": [
    "owner",
    "repo",
    "path"
  ],
  "title": "get_fileArguments",
  "type": "object"
}
```
- `github_get_readme`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    },
    "ref": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Ref"
    }
  },
  "required": [
    "owner",
    "repo"
  ],
  "title": "get_readmeArguments",
  "type": "object"
}
```
- `github_search_code`: No description provided.
```json
{
  "properties": {
    "query": {
      "title": "Query",
      "type": "string"
    },
    "per_page": {
      "default": 10,
      "title": "Per Page",
      "type": "integer"
    }
  },
  "required": [
    "query"
  ],
  "title": "search_codeArguments",
  "type": "object"
}
```
- `github_list_issues`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    },
    "state": {
      "default": "open",
      "title": "State",
      "type": "string"
    },
    "per_page": {
      "default": 20,
      "title": "Per Page",
      "type": "integer"
    },
    "page": {
      "default": 1,
      "title": "Page",
      "type": "integer"
    }
  },
  "required": [
    "owner",
    "repo"
  ],
  "title": "list_issuesArguments",
  "type": "object"
}
```
- `github_get_issue`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    },
    "issue_number": {
      "title": "Issue Number",
      "type": "integer"
    }
  },
  "required": [
    "owner",
    "repo",
    "issue_number"
  ],
  "title": "get_issueArguments",
  "type": "object"
}
```
- `github_create_issue`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    },
    "title": {
      "title": "Title",
      "type": "string"
    },
    "body": {
      "default": "",
      "title": "Body",
      "type": "string"
    },
    "assignees": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Assignees"
    },
    "labels": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Labels"
    }
  },
  "required": [
    "owner",
    "repo",
    "title"
  ],
  "title": "create_issueArguments",
  "type": "object"
}
```
- `github_list_issue_comments`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    },
    "issue_number": {
      "title": "Issue Number",
      "type": "integer"
    },
    "per_page": {
      "default": 20,
      "title": "Per Page",
      "type": "integer"
    },
    "page": {
      "default": 1,
      "title": "Page",
      "type": "integer"
    }
  },
  "required": [
    "owner",
    "repo",
    "issue_number"
  ],
  "title": "list_issue_commentsArguments",
  "type": "object"
}
```
- `github_list_pull_requests`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    },
    "state": {
      "default": "open",
      "title": "State",
      "type": "string"
    },
    "per_page": {
      "default": 20,
      "title": "Per Page",
      "type": "integer"
    },
    "page": {
      "default": 1,
      "title": "Page",
      "type": "integer"
    }
  },
  "required": [
    "owner",
    "repo"
  ],
  "title": "list_pull_requestsArguments",
  "type": "object"
}
```
- `github_get_pull_request`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    },
    "pull_number": {
      "title": "Pull Number",
      "type": "integer"
    }
  },
  "required": [
    "owner",
    "repo",
    "pull_number"
  ],
  "title": "get_pull_requestArguments",
  "type": "object"
}
```
- `github_create_pull_request`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    },
    "title": {
      "title": "Title",
      "type": "string"
    },
    "head": {
      "title": "Head",
      "type": "string"
    },
    "base": {
      "title": "Base",
      "type": "string"
    },
    "body": {
      "default": "",
      "title": "Body",
      "type": "string"
    }
  },
  "required": [
    "owner",
    "repo",
    "title",
    "head",
    "base"
  ],
  "title": "create_pull_requestArguments",
  "type": "object"
}
```
- `github_list_branches`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    },
    "per_page": {
      "default": 50,
      "title": "Per Page",
      "type": "integer"
    }
  },
  "required": [
    "owner",
    "repo"
  ],
  "title": "list_branchesArguments",
  "type": "object"
}
```
- `github_list_commits`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    },
    "sha": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Sha"
    },
    "per_page": {
      "default": 20,
      "title": "Per Page",
      "type": "integer"
    }
  },
  "required": [
    "owner",
    "repo"
  ],
  "title": "list_commitsArguments",
  "type": "object"
}
```
- `github_get_commit`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    },
    "ref": {
      "title": "Ref",
      "type": "string"
    }
  },
  "required": [
    "owner",
    "repo",
    "ref"
  ],
  "title": "get_commitArguments",
  "type": "object"
}
```
- `github_create_branch`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    },
    "new_branch": {
      "title": "New Branch",
      "type": "string"
    },
    "from_branch": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "From Branch"
    },
    "from_sha": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "From Sha"
    }
  },
  "required": [
    "owner",
    "repo",
    "new_branch"
  ],
  "title": "create_branchArguments",
  "type": "object"
}
```
- `github_create_or_update_file`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    },
    "path": {
      "title": "Path",
      "type": "string"
    },
    "message": {
      "title": "Message",
      "type": "string"
    },
    "content": {
      "title": "Content",
      "type": "string"
    },
    "sha": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Sha"
    },
    "branch": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Branch"
    }
  },
  "required": [
    "owner",
    "repo",
    "path",
    "message",
    "content"
  ],
  "title": "create_or_update_fileArguments",
  "type": "object"
}
```
- `github_delete_file`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    },
    "path": {
      "title": "Path",
      "type": "string"
    },
    "message": {
      "title": "Message",
      "type": "string"
    },
    "sha": {
      "title": "Sha",
      "type": "string"
    },
    "branch": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Branch"
    }
  },
  "required": [
    "owner",
    "repo",
    "path",
    "message",
    "sha"
  ],
  "title": "delete_fileArguments",
  "type": "object"
}
```
- `github_list_languages`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    }
  },
  "required": [
    "owner",
    "repo"
  ],
  "title": "list_languagesArguments",
  "type": "object"
}
```
- `github_list_workflows`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    }
  },
  "required": [
    "owner",
    "repo"
  ],
  "title": "list_workflowsArguments",
  "type": "object"
}
```
- `github_trigger_workflow`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    },
    "workflow_id": {
      "title": "Workflow Id",
      "type": "string"
    },
    "ref": {
      "title": "Ref",
      "type": "string"
    },
    "inputs": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Inputs"
    }
  },
  "required": [
    "owner",
    "repo",
    "workflow_id",
    "ref"
  ],
  "title": "trigger_workflowArguments",
  "type": "object"
}
```
- `github_get_workflow_run`: No description provided.
```json
{
  "properties": {
    "owner": {
      "title": "Owner",
      "type": "string"
    },
    "repo": {
      "title": "Repo",
      "type": "string"
    },
    "run_id": {
      "title": "Run Id",
      "type": "integer"
    }
  },
  "required": [
    "owner",
    "repo",
    "run_id"
  ],
  "title": "get_workflow_runArguments",
  "type": "object"
}
```
### `google_drive` tools (19)
- `google_drive_list_files`: List recent non-trashed Drive files and folders visible to the connected account.
```json
{
  "properties": {
    "page_size": {
      "default": 20,
      "title": "Page Size",
      "type": "integer"
    }
  },
  "required": [],
  "title": "list_filesArguments",
  "type": "object"
}
```
- `google_drive_list_root`: List the direct contents of Drive root or the configured Drive root folder when one is set.
```json
{
  "properties": {
    "page_size": {
      "default": 20,
      "title": "Page Size",
      "type": "integer"
    }
  },
  "required": [],
  "title": "list_rootArguments",
  "type": "object"
}
```
- `google_drive_search_files`: Search Drive files by filename or title. Natural-language requests that include a filename are supported.
```json
{
  "properties": {
    "query": {
      "title": "Query",
      "type": "string"
    },
    "page_size": {
      "default": 20,
      "title": "Page Size",
      "type": "integer"
    }
  },
  "required": [
    "query"
  ],
  "title": "search_filesArguments",
  "type": "object"
}
```
- `google_drive_search_full_text`: Search Drive file contents using Drive full-text search, with optional MIME type filters.
```json
{
  "properties": {
    "query": {
      "title": "Query",
      "type": "string"
    },
    "page_size": {
      "default": 20,
      "title": "Page Size",
      "type": "integer"
    },
    "mime_filters": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Mime Filters"
    }
  },
  "required": [
    "query"
  ],
  "title": "search_full_textArguments",
  "type": "object"
}
```
- `google_drive_list_folder`: List the direct contents of a Drive folder when you already know its folder ID.
```json
{
  "properties": {
    "folder_id": {
      "title": "Folder Id",
      "type": "string"
    },
    "page_size": {
      "default": 50,
      "title": "Page Size",
      "type": "integer"
    }
  },
  "required": [
    "folder_id"
  ],
  "title": "list_folderArguments",
  "type": "object"
}
```
- `google_drive_list_shared_with_me`: List non-trashed Drive files currently shared with the connected account.
```json
{
  "properties": {
    "page_size": {
      "default": 20,
      "title": "Page Size",
      "type": "integer"
    }
  },
  "required": [],
  "title": "list_shared_with_meArguments",
  "type": "object"
}
```
- `google_drive_get_metadata`: Return Drive metadata for a specific file or folder ID.
```json
{
  "properties": {
    "file_id": {
      "title": "File Id",
      "type": "string"
    }
  },
  "required": [
    "file_id"
  ],
  "title": "get_metadataArguments",
  "type": "object"
}
```
- `google_drive_read_text_file`: Read the text content of a Drive file. Supports Google Docs, Google Sheets, PDF, DOCX, TXT, CSV, JSON, Markdown, and other text-like files.
```json
{
  "properties": {
    "file_id": {
      "title": "File Id",
      "type": "string"
    }
  },
  "required": [
    "file_id"
  ],
  "title": "read_text_fileArguments",
  "type": "object"
}
```
- `google_drive_search_and_read_file`: Search for the best matching Drive file by name and immediately return its readable content when possible.
```json
{
  "properties": {
    "query": {
      "title": "Query",
      "type": "string"
    },
    "page_size": {
      "default": 10,
      "title": "Page Size",
      "type": "integer"
    }
  },
  "required": [
    "query"
  ],
  "title": "search_and_read_fileArguments",
  "type": "object"
}
```
- `google_drive_resolve_path`: Resolve a slash-delimited Drive folder path relative to Drive root or the configured root folder.
```json
{
  "properties": {
    "path": {
      "title": "Path",
      "type": "string"
    }
  },
  "required": [
    "path"
  ],
  "title": "resolve_pathArguments",
  "type": "object"
}
```
- `google_drive_export_google_doc`: Export a Google Doc into a target textual format such as plain text.
```json
{
  "properties": {
    "file_id": {
      "title": "File Id",
      "type": "string"
    },
    "mime_type": {
      "default": "text/plain",
      "title": "Mime Type",
      "type": "string"
    }
  },
  "required": [
    "file_id"
  ],
  "title": "export_google_docArguments",
  "type": "object"
}
```
- `google_drive_export_sheet_csv`: Export a Google Sheet as CSV text.
```json
{
  "properties": {
    "file_id": {
      "title": "File Id",
      "type": "string"
    }
  },
  "required": [
    "file_id"
  ],
  "title": "export_sheet_csvArguments",
  "type": "object"
}
```
- `google_drive_create_folder`: Create a new Drive folder, optionally under a parent folder ID.
```json
{
  "properties": {
    "name": {
      "title": "Name",
      "type": "string"
    },
    "parent_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Parent Id"
    }
  },
  "required": [
    "name"
  ],
  "title": "create_folderArguments",
  "type": "object"
}
```
- `google_drive_upload_text_file`: Upload a new text file to Drive, optionally inside a parent folder.
```json
{
  "properties": {
    "name": {
      "title": "Name",
      "type": "string"
    },
    "content": {
      "title": "Content",
      "type": "string"
    },
    "parent_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Parent Id"
    },
    "mime_type": {
      "default": "text/plain",
      "title": "Mime Type",
      "type": "string"
    }
  },
  "required": [
    "name",
    "content"
  ],
  "title": "upload_text_fileArguments",
  "type": "object"
}
```
- `google_drive_create_text_file_at_path`: Create a text file at an existing slash-delimited Drive path relative to root or the configured root folder.
```json
{
  "properties": {
    "path": {
      "title": "Path",
      "type": "string"
    },
    "content": {
      "title": "Content",
      "type": "string"
    },
    "mime_type": {
      "default": "text/plain",
      "title": "Mime Type",
      "type": "string"
    }
  },
  "required": [
    "path",
    "content"
  ],
  "title": "create_text_file_at_pathArguments",
  "type": "object"
}
```
- `google_drive_update_text_file`: Replace the content of an existing Drive text file.
```json
{
  "properties": {
    "file_id": {
      "title": "File Id",
      "type": "string"
    },
    "content": {
      "title": "Content",
      "type": "string"
    },
    "mime_type": {
      "default": "text/plain",
      "title": "Mime Type",
      "type": "string"
    }
  },
  "required": [
    "file_id",
    "content"
  ],
  "title": "update_text_fileArguments",
  "type": "object"
}
```
- `google_drive_delete_file`: Delete a Drive file or folder by ID.
```json
{
  "properties": {
    "file_id": {
      "title": "File Id",
      "type": "string"
    }
  },
  "required": [
    "file_id"
  ],
  "title": "delete_fileArguments",
  "type": "object"
}
```
- `google_drive_move_file`: Move a Drive file or folder into a different parent folder ID.
```json
{
  "properties": {
    "file_id": {
      "title": "File Id",
      "type": "string"
    },
    "new_parent_id": {
      "title": "New Parent Id",
      "type": "string"
    }
  },
  "required": [
    "file_id",
    "new_parent_id"
  ],
  "title": "move_fileArguments",
  "type": "object"
}
```
- `google_drive_share_file`: Share a Drive file with a user email using the requested permission role.
```json
{
  "properties": {
    "file_id": {
      "title": "File Id",
      "type": "string"
    },
    "email": {
      "title": "Email",
      "type": "string"
    },
    "role": {
      "default": "reader",
      "title": "Role",
      "type": "string"
    },
    "permission_type": {
      "default": "user",
      "title": "Permission Type",
      "type": "string"
    }
  },
  "required": [
    "file_id",
    "email"
  ],
  "title": "share_fileArguments",
  "type": "object"
}
```

## GitHub Validation
- GitHub identity lookup failed: `Error executing tool get_authenticated_user: Client error '401 Unauthorized' for url 'https://api.github.com/user'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/401`

## Google Drive Validation
- Root listing count: **2**
| Name | Mime | Modified | Size |
| --- | --- | --- | --- |
| tcs | application/vnd.google-apps.folder | 2026-03-14T14:03:08.067Z |  |
| Google AI Studio | application/vnd.google-apps.folder | 2026-02-19T07:20:44.922Z |  |
### Search Results
| Name | ID | Mime | Modified | Parent |
| --- | --- | --- | --- | --- |
| can you build the project that conducts the tests for the for the student for the tcs exam for pr... | 1_N5w3W5... | application/vnd.google-makersuite.prompt | 2026-02-19T07:20:54.179Z | Google AI Studio |
### Drive Read: `can you build the project that conducts the tests for the for the student for the tcs exam for pr...` (application/vnd.google-makersuite.prompt)
### Folder Structure: `Google AI Studio`
- applet_access_history.json
- can you build the project that conducts the tests for the for the student for the tcs exam for pr...
- TCS Ninja & Digital Prep Hub
- Created Drive file ID: `1oJSsbvV...`
```text
# MCP Super Test 2026-03-15

- Generated at (IST): 2026-03-15T10:32:21.021689+05:30
- Backend user: admin
- Connector user: admin

## GitHub Results
- Identity, repo metadata, code search, issues, pull requests, and write validation summary.

## Drive Results
- Root listing, full-text search, conten
```

## Combined Workflows And Failure Injection
- No roadmap-like Drive document was found for project sync simulation.
### Failure Injection
| Scenario | Observed Error | Recovery |
| --- | --- | --- |
| Drive missing file | Error executing tool read_text_file: Client error '404 Not Found' for url 'https://www.googleapis.com/drive/v3/files/super-secret-fake-12345?fields=id%2Cname%2CmimeType%2CmodifiedTime%2Csize%2CwebViewLink&supportsAllDrives=true'<br>For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/404 | Use a real Drive file ID or reconnect Drive if content access is missing. |
| Drive no-match search | No matching Drive file was found. | Verify the filename or broaden the query. |
| GitHub fake user | Error executing tool list_user_repositories: Client error '401 Unauthorized' for url 'https://api.github.com/users/nonexistentuser987654321/repos?sort=updated&per_page=10&page=1'<br>For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/401 | Verify the GitHub owner/login before retrying repository enumeration. |
| Drive impossible path | Error executing tool create_text_file_at_path: Drive folder path '/This/Folder/Does/Not/Exist' does not exist or is ambiguous | Create the folder path first or use a valid parent path. |

## Check Outcomes
- `discovery` / `backend-preflight`: `pass` - Authenticated to localhost backend and loaded connector status.
- `discovery` / `tool-enumeration`: `pass` - Enumerated runtime MCP tools and schemas for both servers.
- `auth` / `github-identity`: `blocked-by-permission` - GitHub identity lookup failed: Error executing tool get_authenticated_user: Client error '401 Unauthorized' for url 'https://api.github.com/user'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/401
- `list` / `drive-root-listing`: `pass` - Listed 2 root items.
- `search` / `drive-search`: `pass` - Collected 1 Drive search hits.
- `read` / `drive-read-files`: `pass` - Read 1 Drive files across distinct types.
- `list` / `drive-folder-navigation`: `pass` - Mapped a two-level Drive folder tree for `Google AI Studio`.
- `write` / `drive-create-file`: `pass` - Created and verified Drive file `1oJSsbvV...`.
- `write` / `drive-delete-temp-file`: `pass` - Deleted temporary Drive file `1oJSsbvV...`.
- `combined` / `project-sync`: `partial` - No roadmap-like Drive document was found for project sync simulation.
- `failure` / `failure-injection`: `pass` - Captured failure behavior for missing Drive file, fake GitHub user, and impossible Drive path.

## Final Summary
- Servers discovered and connected: GitHub `True`, Google Drive `True`
- Success rate per category (partial counts as 50%):
| Category | Score | Pass | Partial | Blocked | Error |
| --- | --- | --- | --- | --- | --- |
| discovery | 100% | 2 | 0 | 0 | 0 |
| auth | 0% | 0 | 0 | 1 | 0 |
| list | 100% | 2 | 0 | 0 | 0 |
| read | 100% | 1 | 0 | 0 | 0 |
| search | 100% | 1 | 0 | 0 | 0 |
| write | 100% | 2 | 0 | 0 | 0 |
| combined | 50% | 0 | 1 | 0 | 0 |
| failure | 100% | 1 | 0 | 0 | 0 |
- Most useful demonstrated capability: Runtime MCP discovery and authenticated connector preflight across both servers.
- Bugs, limitations, or permission issues:
  - `github-identity`: `blocked-by-permission` - GitHub identity lookup failed: Error executing tool get_authenticated_user: Client error '401 Unauthorized' for url 'https://api.github.com/user'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/401
  - `project-sync`: `partial` - No roadmap-like Drive document was found for project sync simulation.
- Recommendations:
  - Run the validator with non-sandboxed network access; sandboxed MCP stdio calls in this environment cannot reach GitHub/Google directly.
  - Keep the new GitHub scope/org/comment/language tools and Drive root/full-text/path tools in the server surface; they materially improve audit coverage.
  - If Drive remains on `drive.file` rather than full `drive`, expect content visibility limits for files not created or explicitly opened by the app.

## Tool Trace
1. Server `github`; tool `github_get_token_info`; why: Verify authenticated GitHub identity and token metadata.; expected: Expected login, profile URL, and scope headers if GitHub returns them.; status: `blocked-by-permission`
   - Arguments: `{}`
   - Result note: `Error executing tool get_token_info: Client error '401 Unauthorized' for url 'https://api.github.com/user'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/401`
2. Server `github`; tool `github_get_authenticated_user`; why: Fallback identity check when token info is unavailable.; expected: Expected login, profile URL, and repo counts.; status: `blocked-by-permission`
   - Arguments: `{}`
   - Result note: `Error executing tool get_authenticated_user: Client error '401 Unauthorized' for url 'https://api.github.com/user'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/401`
3. Server `google_drive`; tool `google_drive_list_root`; why: List direct contents of Drive root.; expected: Expected recent items under Drive root or configured root folder.; status: `pass`
   - Arguments: `{"page_size": 100}`
   - Result note: `ok`
4. Server `google_drive`; tool `google_drive_search_full_text`; why: Search Drive content for project-related keywords.; expected: Expected files whose body text matches any requested keyword.; status: `pass`
   - Arguments: `{"query": "agent MCP project test todo roadmap", "page_size": 50, "mime_filters": ["application/vnd.google-apps.document", "application/vnd.google-apps.spreadsheet", "text/plain", "text/markdown", "application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/json", "application/csv"]}`
   - Result note: `ok`
5. Server `google_drive`; tool `google_drive_search_files`; why: Fallback filename search for `agent`.; expected: Expected Drive files whose names match the keyword.; status: `pass`
   - Arguments: `{"query": "agent", "page_size": 20}`
   - Result note: `ok`
6. Server `google_drive`; tool `google_drive_search_files`; why: Fallback filename search for `MCP`.; expected: Expected Drive files whose names match the keyword.; status: `pass`
   - Arguments: `{"query": "MCP", "page_size": 20}`
   - Result note: `ok`
7. Server `google_drive`; tool `google_drive_search_files`; why: Fallback filename search for `project`.; expected: Expected Drive files whose names match the keyword.; status: `pass`
   - Arguments: `{"query": "project", "page_size": 20}`
   - Result note: `ok`
8. Server `google_drive`; tool `google_drive_search_files`; why: Fallback filename search for `test`.; expected: Expected Drive files whose names match the keyword.; status: `pass`
   - Arguments: `{"query": "test", "page_size": 20}`
   - Result note: `ok`
9. Server `google_drive`; tool `google_drive_search_files`; why: Fallback filename search for `todo`.; expected: Expected Drive files whose names match the keyword.; status: `pass`
   - Arguments: `{"query": "todo", "page_size": 20}`
   - Result note: `ok`
10. Server `google_drive`; tool `google_drive_search_files`; why: Fallback filename search for `roadmap`.; expected: Expected Drive files whose names match the keyword.; status: `pass`
   - Arguments: `{"query": "roadmap", "page_size": 20}`
   - Result note: `ok`
11. Server `google_drive`; tool `google_drive_get_metadata`; why: Resolve parent metadata for Drive item `can you build the project that conducts the tests for the for the student for the tcs exam for pr...`.; expected: Expected parent folder metadata.; status: `pass`
   - Arguments: `{"file_id": "14QzBfI6-gFzFfKPnjaMFIUu7DODfrFDi"}`
   - Result note: `ok`
12. Server `google_drive`; tool `google_drive_read_text_file`; why: Read Drive content for `can you build the project that conducts the tests for the for the student for the tcs exam for pr...`.; expected: Expected readable text content or a clear extraction warning.; status: `pass`
   - Arguments: `{"file_id": "1_N5w3W5XmZyujoyDmH5MmjrIQZ7Kw7b4"}`
   - Result note: `ok`
13. Server `google_drive`; tool `google_drive_search_files`; why: Search for project-related Drive folders named `AI`.; expected: Expected folder candidates when such folders exist.; status: `pass`
   - Arguments: `{"query": "AI", "page_size": 20}`
   - Result note: `ok`
14. Server `google_drive`; tool `google_drive_search_files`; why: Search for project-related Drive folders named `Projects`.; expected: Expected folder candidates when such folders exist.; status: `pass`
   - Arguments: `{"query": "Projects", "page_size": 20}`
   - Result note: `ok`
15. Server `google_drive`; tool `google_drive_search_files`; why: Search for project-related Drive folders named `Agent`.; expected: Expected folder candidates when such folders exist.; status: `pass`
   - Arguments: `{"query": "Agent", "page_size": 20}`
   - Result note: `ok`
16. Server `google_drive`; tool `google_drive_search_files`; why: Search for project-related Drive folders named `2026`.; expected: Expected folder candidates when such folders exist.; status: `pass`
   - Arguments: `{"query": "2026", "page_size": 20}`
   - Result note: `ok`
17. Server `google_drive`; tool `google_drive_list_folder`; why: List direct contents of Drive folder `Google AI Studio`.; expected: Expected children of the selected Drive folder.; status: `pass`
   - Arguments: `{"folder_id": "14QzBfI6-gFzFfKPnjaMFIUu7DODfrFDi", "page_size": 50}`
   - Result note: `ok`
18. Server `google_drive`; tool `google_drive_search_files`; why: Look for an `AI-Tests` Drive folder before creating the validation file.; expected: Expected zero or one folder named `AI-Tests`.; status: `pass`
   - Arguments: `{"query": "AI-Tests", "page_size": 10}`
   - Result note: `ok`
19. Server `google_drive`; tool `google_drive_upload_text_file`; why: Create a Drive markdown file for validation evidence.; expected: Expected a newly created Drive text file.; status: `pass`
   - Arguments: `{"name": "MCP-Super-Test-2026-03-15.md", "content": "# MCP Super Test 2026-03-15\n\n- Generated at (IST): 2026-03-15T10:32:21.021689+05:30\n- Backend user: admin\n- Connector user: admin\n\n## GitHub Results\n- Identity, repo metadata, code search, issues, pull requests, and write validation summary.\n\n## Drive Results\n- Root listing, full-text search, content reads, folder navigation, and write validation summary.\n\n## Outcome\n- Successes and failures will be copied into the final markdown report.", "mime_type": "text/markdown"}`
   - Result note: `ok`
20. Server `google_drive`; tool `google_drive_search_files`; why: Search for the newly created Drive validation file by name.; expected: Expected the created Drive file to appear in search results.; status: `pass`
   - Arguments: `{"query": "MCP-Super-Test-2026-03-15.md", "page_size": 10}`
   - Result note: `ok`
21. Server `google_drive`; tool `google_drive_read_text_file`; why: Read back the newly created Drive validation file.; expected: Expected markdown content from the new file.; status: `pass`
   - Arguments: `{"file_id": "1oJSsbvVFBvms9jXuSMgNmDNTtjT-9IEo"}`
   - Result note: `ok`
22. Server `google_drive`; tool `google_drive_delete_file`; why: Delete the temporary Drive validation file after verification.; expected: Expected Drive file deletion to succeed.; status: `pass`
   - Arguments: `{"file_id": "1oJSsbvVFBvms9jXuSMgNmDNTtjT-9IEo"}`
   - Result note: `ok`
23. Server `google_drive`; tool `google_drive_search_full_text`; why: Search Drive for planning documents to seed cross-MCP project sync validation.; expected: Expected a planning document with roadmap-like content.; status: `pass`
   - Arguments: `{"query": "roadmap plan next steps agent", "page_size": 10, "mime_filters": ["application/vnd.google-apps.document", "application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain", "text/markdown"]}`
   - Result note: `ok`
24. Server `google_drive`; tool `google_drive_read_text_file`; why: Validate Drive missing-file failure handling with a bogus file ID.; expected: Expected a clear not-found error.; status: `partial`
   - Arguments: `{"file_id": "super-secret-fake-12345"}`
   - Result note: `Error executing tool read_text_file: Client error '404 Not Found' for url 'https://www.googleapis.com/drive/v3/files/super-secret-fake-12345?fields=id%2Cname%2CmimeType%2CmodifiedTime%2Csize%2CwebViewLink&supportsAllDrives=true'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/404`
25. Server `google_drive`; tool `google_drive_search_and_read_file`; why: Validate graceful no-match behavior for a non-existent Drive filename.; expected: Expected a no-match response without an exception.; status: `pass`
   - Arguments: `{"query": "super-secret-fake-12345.pdf", "page_size": 10}`
   - Result note: `ok`
26. Server `github`; tool `github_list_user_repositories`; why: Validate GitHub fake-user failure handling.; expected: Expected a 404-style error for the bogus GitHub account.; status: `blocked-by-permission`
   - Arguments: `{"owner": "nonexistentuser987654321", "per_page": 10, "page": 1}`
   - Result note: `Error executing tool list_user_repositories: Client error '401 Unauthorized' for url 'https://api.github.com/users/nonexistentuser987654321/repos?sort=updated&per_page=10&page=1'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/401`
27. Server `google_drive`; tool `google_drive_create_text_file_at_path`; why: Validate Drive path-resolution failure handling on an impossible nested path.; expected: Expected a path-resolution error before upload.; status: `partial`
   - Arguments: `{"path": "/This/Folder/Does/Not/Exist/test.txt", "content": "validation", "mime_type": "text/plain"}`
   - Result note: `Error executing tool create_text_file_at_path: Drive folder path '/This/Folder/Does/Not/Exist' does not exist or is ambiguous`
