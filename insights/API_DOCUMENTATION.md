# React Page Builder API Documentation

This document outlines the API structure for the React Page Builder, detailing endpoints, data structures, and workflows for seamless page creation and management.

## Authentication

All API endpoints require authentication using an API key. Include the API key in the header of each request:

```
X-Api-Key: your-api-key-here
```

## 1. Core API Endpoints

### 1.1 Pages API

| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|--------------|----------|
| `/api/pages/` | GET | List all pages | N/A | List of page objects with basic info |
| `/api/pages/` | POST | Create a new page | See [Page Create Request](#211-pagecreate-request) | Created page with ID |
| `/api/pages/{id}/` | GET | Get page details | N/A | Complete page details |
| `/api/pages/{id}/` | PUT/PATCH | Update page details | See [Page Update Request](#212-page-update-request) | Updated page |
| `/api/pages/{id}/` | DELETE | Delete a page | N/A | 204 No Content |
| `/api/pages/{id}/full/` | GET | Get complete page with layout and components | N/A | Complete page with layout and components |
| `/api/pages/{id}/publish/` | POST | Publish/unpublish a page | See [Publish Request](#213-publish-request) | Updated page |
| `/api/pages/{id}/delete/` | DELETE | Delete a page with all its components | N/A | 204 No Content |
| `/api/pages/{id}/full-update/` | PUT | Update page, layout, and components in one call | See [Complete Page Update Request](#214-complete-page-update-request) | Updated page with all data |

### 1.2 Components API

| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|--------------|----------|
| `/api/component-types/` | GET | List all available component types | N/A | List of component types |
| `/api/pages/{page_id}/components/` | GET | List all components for a page | N/A | List of component instances |
| `/api/pages/{page_id}/components/` | POST | Add a component to a page | See [Component Create Request](#221-component-create-request) | Created component |
| `/api/pages/{page_id}/components/{id}/` | GET | Get component details | N/A | Component details |
| `/api/pages/{page_id}/components/{id}/` | PUT/PATCH | Update a component | See [Component Update Request](#222-component-update-request) | Updated component |
| `/api/pages/{page_id}/components/{id}/` | DELETE | Remove a component | N/A | 204 No Content |
| `/api/pages/{page_id}/components/bulk/` | POST | Bulk create/update components | See [Bulk Component Update Request](#223-bulk-component-update-request) | Array of created/updated components |

### 1.3 Analytics API

| Endpoint | Method | Description | Query Parameters | Response |
|----------|--------|-------------|-----------------|----------|
| `/api/session-analytics/daily_sessions/` | GET | Get daily session counts | `days`: Number of days (default: 30) | Daily session data |
| `/api/session-analytics/request_medium_distribution/` | GET | Get request medium distribution | `days`, `company_id` | Medium distribution data |
| `/api/session-analytics/company_session_comparison/` | GET | Get company-wise session usage | `days`, `limit` | Company usage data |
| `/api/session-analytics/api_controller_usage/` | GET | Get API controller usage | `days`, `company_id` | Controller usage data |
| `/api/session-analytics/total_api_controllers/` | GET | Get total API controllers count | `company_id`, `active_only` | Total controllers and stats |

### 1.3.1 Daily Sessions

Get the count of sessions created daily for a specified number of days.

**Endpoint:** `/api/v1/react-page-builder/api/session-analytics/daily_sessions/`

**Method:** GET

**Query Parameters:**
- `days` (optional): Number of days to fetch data for (default: 30)

**Response:**
```json
{
  "data": [
    {
      "date": "01 Apr, 2025",
      "count": 35
    },
    {
      "date": "02 Apr, 2025",
      "count": 42
    },
    {
      "date": "03 Apr, 2025",
      "count": 38
    }
    // ... more daily data
  ]
}
```

### 1.3.2 Request Medium Distribution

Get the distribution of request mediums used in conversations.

**Endpoint:** `/api/v1/react-page-builder/api/session-analytics/request_medium_distribution/`

**Method:** GET

**Query Parameters:**
- `days` (optional): Number of days to fetch data for (default: 30)
- `company_id` (optional): Filter by company ID

**Response:**
```json
{
  "data": [
    {
      "name": "API",
      "value": 120,
      "percentage": 45.28
    },
    {
      "name": "Whatsapp Meta Cloud API",
      "value": 85,
      "percentage": 32.07
    },
    {
      "name": "Python SDK",
      "value": 60,
      "percentage": 22.65
    }
    // ... more mediums
  ],
  "total": 265
}
```

### 1.3.3 Company Session Comparison

Get company-wise session usage comparison.

**Endpoint:** `/api/v1/react-page-builder/api/session-analytics/company_session_comparison/`

**Method:** GET

**Query Parameters:**
- `days` (optional): Number of days to fetch data for (default: 30)
- `limit` (optional): Maximum number of companies to include (default: 10)

**Response:**
```json
{
  "data": [
    {
      "company": "Acme Corp",
      "sessions": 250
    },
    {
      "company": "Globex Inc",
      "sessions": 180
    },
    {
      "company": "Initech",
      "sessions": 145
    }
    // ... more companies
  ]
}
```

### 1.3.4 API Controller Usage

Get count of each API controller used in conversations, company-wise.

**Endpoint:** `/api/v1/react-page-builder/api/session-analytics/api_controller_usage/`

**Method:** GET

**Query Parameters:**
- `days` (optional): Number of days to fetch data for (default: 30)
- `company_id` (optional): Filter by company ID

**Response:**
```json
{
  "data": [
    {
      "name": "Order Processing Controller",
      "value": 145
    },
    {
      "name": "Customer Support Controller",
      "value": 98
    },
    {
      "name": "Inventory Management Controller",
      "value": 76
    }
    // ... more controllers
  ]
}
```

### 1.3.5 Total API Controllers

Get the total number of API controllers with additional statistics.

**Endpoint:** `/api/v1/react-page-builder/api/session-analytics/total_api_controllers/`

**Method:** GET

**Response:**
```json
{
  "heading": "Total Workflows",
  "Value": 45,
  "sub-heading": "across 6 companies"
}
```

### 1.4 Page Layout API

| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|--------------|----------|
| `/api/pages/{page_id}/layout/` | GET | Get page layout | N/A | Layout configuration |
| `/api/pages/{page_id}/layout/` | PUT | Update page layout | See [Layout Update Request](#231-layout-update-request) | Updated layout |

### 1.5 Component Data API

The Component Data API provides data for various dashboard visualization components.

### 1.5.1 Base URL

All component data API endpoints are relative to the base URL:

```
/api/v1/react-page-builder/api/component-data/
```

### 1.5.2 Available Component Data Endpoints

| Endpoint | Method | Description | Query Parameters | Response |
|----------|--------|-------------|-----------------|----------|
| `/api/component-data/kpi_card/` | GET | Get KPI card data | `component_instance_id` | KPI data with value and trend |
| `/api/component-data/line_chart/` | GET | Get line chart data | `component_instance_id` | Time series data for charts |
| `/api/component-data/bar_chart/` | GET | Get bar chart data | `component_instance_id` | Categorical data for bar charts |
| `/api/component-data/pie_chart/` | GET | Get pie chart data | `component_instance_id` | Distribution data for pie charts |
| `/api/component-data/table/` | GET | Get table data | `component_instance_id` | Tabular data with headers and rows |
| `/api/component-data/chat_analytics/` | GET | Get chat analytics data | `component_instance_id` | Various chat analytics metrics |

## 2. Data Structures

### 2.1 Page API Request/Response Examples

#### 2.1.1 Page Create Request
```json
{
  "title": "My Page",
  "slug": "my-page",
  "description": "This is my page description",
  "is_published": false
}
```

**Field Explanations:**
- `title`: The display name of the page (required)
- `slug`: URL-friendly identifier for the page, must be unique (required)
- `description`: Optional text describing the page's purpose
- `is_published`: Boolean flag indicating whether the page is visible to users

#### 2.1.2 Page Update Request
```json
{
  "title": "Updated Page Title",
  "slug": "updated-slug",
  "description": "Updated description",
  "is_published": false
}
```

**Field Explanations:**
- All fields are optional during update - only include fields you want to change
- Changing the `slug` will affect the page's URL

#### 2.1.3 Publish Request
```json
{
  "is_published": true
}
```

**Field Explanations:**
- `is_published`: Set to `true` to make the page visible to users, `false` to hide it
- This is a dedicated endpoint for quickly changing a page's publication status

#### 2.1.4 Complete Page Update Request
```json
{
  "page": {
    "title": "Updated Page Title",
    "slug": "updated-slug",
    "description": "Updated description",
    "is_published": true
  },
  "layout": {
    "layout_config": {
      "columns": 12,
      "rowHeight": 30,
      "containerPadding": [10, 10]
    }
  },
  "components": [
    {
      "id": 1,
      "title": "Component 1",
      "position": { "x": 0, "y": 0, "w": 6, "h": 4 }
    },
    {
      "component_type": 2,
      "title": "New Component",
      "instance_id": "new-instance-id",
      "config": {},
      "position": { "x": 6, "y": 0, "w": 6, "h": 4 }
    }
  ],
  "removed_components": [3, 4]
}
```

**Field Explanations:**
- `page`: Contains basic page metadata (same fields as in Page Update)
- `layout`: Defines the grid layout configuration for the page
  - `columns`: Number of grid columns (typically 12 for responsive design)
  - `rowHeight`: Height of each grid row in pixels
  - `containerPadding`: Padding around the grid container [horizontal, vertical]
- `components`: Array of components to add or update on the page
  - For existing components, include the `id`
  - For new components, include `component_type` and `instance_id`
  - `component_type`: ID reference to a specific component type in the database
  - `instance_id`: Unique identifier for this specific component instance
  - `position`: Grid positioning with x/y coordinates and width/height in grid units
- `removed_components`: Array of component IDs to remove from the page

### 2.2 Component API Request/Response Examples

#### 2.2.1 Component Create Request
```json
{
  "component_type": 1,
  "title": "My Component",
  "instance_id": "unique-instance-id",
  "config": {
    "property1": "value1",
    "property2": "value2"
  },
  "position": {
    "x": 0,
    "y": 0,
    "w": 6,
    "h": 4
  },
  "data_source": {
    "source_id": 1,
    "query_params": {}
  }
}
```

**Field Explanations:**
- `component_type`: ID reference to a specific component type in the database (required)
- `title`: Display name for this component instance (required)
- `instance_id`: Unique identifier for this component instance (required)
- `config`: Component-specific configuration options as a JSON object
- `position`: Grid positioning parameters
  - `x`: Horizontal position in grid units (from left)
  - `y`: Vertical position in grid units (from top)
  - `w`: Width in grid units
  - `h`: Height in grid units
- `data_source`: Optional configuration for dynamic data loading
  - `source_id`: ID of the data source to use
  - `query_params`: Parameters to pass to the data source

#### 2.2.2 Component Update Request
```json
{
  "title": "Updated Component Title",
  "config": {
    "property1": "new-value1",
    "property2": "new-value2",
    "newProperty": "value"
  },
  "position": {
    "x": 2,
    "y": 1,
    "w": 4,
    "h": 3
  }
}
```

**Field Explanations:**
- All fields are optional during update - only include fields you want to change
- `config` is merged with existing configuration (partial updates supported)
- `position` must include all positioning parameters when updating

#### 2.2.3 Bulk Component Update Request
```json
{
  "components": [
    {
      "id": 1,
      "title": "Updated Component",
      "config": {
        "property1": "value1",
        "property2": "value2"
      },
      "position": {
        "x": 0,
        "y": 0,
        "w": 6,
        "h": 4
      }
    },
    {
      "id": 2,
      "title": "Another Component",
      "config": {
        "property1": "value1"
      },
      "position": {
        "x": 6,
        "y": 0,
        "w": 6,
        "h": 4
      }
    }
  ]
}
```

**Field Explanations:**
- `components`: Array of component objects to update in a single request
- Each component must include its `id` for identification
- Updates are processed as a batch, allowing for efficient repositioning of multiple components
- All updates are applied atomically - either all succeed or none are applied

### 2.3 Layout API Request/Response Examples

#### 2.3.1 Layout Update Request
```json
{
  "layout_config": {
    "columns": 12,
    "rowHeight": 30,
    "containerPadding": [10, 10],
    "margin": [10, 10],
    "isDraggable": true,
    "isResizable": true
  }
}
```

**Field Explanations:**
- `columns`: Number of grid columns (typically 12 for responsive design)
- `rowHeight`: Height of each grid row in pixels
- `containerPadding`: Padding around the grid container [horizontal, vertical]
- `margin`: Margin around the grid container [horizontal, vertical]
- `isDraggable`: Boolean flag indicating whether components can be dragged
- `isResizable`: Boolean flag indicating whether components can be resized

## 3. Response Formats

### 3.1 Success Responses

#### 3.1.1 GET /api/pages/ Response
```json
[
  {
    "id": 1,
    "title": "Home Page",
    "slug": "home",
    "description": "Main landing page",
    "is_published": true,
    "created_at": "2025-03-15T10:30:00Z",
    "updated_at": "2025-03-20T14:45:00Z",
    "layout": {
      "id": 1,
      "page": 1,
      "layout_config": {
        "columns": 12,
        "rowHeight": 30,
        "containerPadding": [10, 10]
      }
    },
    "components": []
  },
  {
    "id": 2,
    "title": "About Us",
    "slug": "about-us",
    "description": "Company information page",
    "is_published": true,
    "created_at": "2025-03-16T09:20:00Z",
    "updated_at": "2025-03-18T11:15:00Z",
    "layout": {
      "id": 2,
      "page": 2,
      "layout_config": {
        "columns": 12,
        "rowHeight": 30,
        "containerPadding": [10, 10]
      }
    },
    "components": []
  }
]
```

#### 3.1.2 GET /api/pages/{id}/ Response
```json
{
  "id": 1,
  "title": "Home Page",
  "slug": "home",
  "description": "Main landing page",
  "is_published": true,
  "created_at": "2025-03-15T10:30:00Z",
  "updated_at": "2025-03-20T14:45:00Z",
  "layout": {
    "id": 1,
    "page": 1,
    "layout_config": {
      "columns": 12,
      "rowHeight": 30,
      "containerPadding": [10, 10]
    }
  },
  "components": []
}
```

#### 3.1.3 GET /api/pages/{id}/full/ Response
```json
{
  "id": 1,
  "title": "Home Page",
  "slug": "home",
  "description": "Main landing page",
  "is_published": true,
  "created_at": "2025-03-15T10:30:00Z",
  "updated_at": "2025-03-20T14:45:00Z",
  "layout": {
    "id": 1,
    "page": 1,
    "layout_config": {
      "columns": 12,
      "rowHeight": 30,
      "containerPadding": [10, 10]
    }
  },
  "components": [
    {
      "id": 1,
      "page": 1,
      "component_type": 1,
      "component_type_details": {
        "id": 1,
        "name": "Text Block",
        "code": "text_block",
        "icon": "text_fields",
        "description": "Simple text content block",
        "default_config": {
          "text": "Default text content",
          "style": "default"
        },
        "is_global": true
      },
      "title": "Welcome Text",
      "instance_id": "welcome-text-1",
      "config": {
        "text": "<h1>Welcome to our website</h1><p>This is our homepage content.</p>",
        "style": "modern"
      },
      "position": {
        "x": 0,
        "y": 0,
        "w": 12,
        "h": 4
      },
      "data_source": null
    },
    {
      "id": 2,
      "page": 1,
      "component_type": 2,
      "component_type_details": {
        "id": 2,
        "name": "Image Gallery",
        "code": "image_gallery",
        "icon": "collections",
        "description": "Display multiple images in a gallery",
        "default_config": {
          "images": [],
          "display_type": "grid"
        },
        "is_global": true
      },
      "title": "Featured Images",
      "instance_id": "featured-images-1",
      "config": {
        "images": [
          {
            "url": "/media/images/image1.jpg",
            "caption": "Image 1"
          },
          {
            "url": "/media/images/image2.jpg",
            "caption": "Image 2"
          }
        ],
        "display_type": "carousel"
      },
      "position": {
        "x": 0,
        "y": 4,
        "w": 12,
        "h": 6
      },
      "data_source": null
    }
  ]
}
```

#### 3.1.4 GET /api/component-types/ Response
```json
[
  {
    "id": 1,
    "name": "Text Block",
    "code": "text_block",
    "icon": "text_fields",
    "description": "Simple text content block",
    "default_config": {
      "text": "Default text content",
      "style": "default"
    },
    "is_global": true
  },
  {
    "id": 2,
    "name": "Image Gallery",
    "code": "image_gallery",
    "icon": "collections",
    "description": "Display multiple images in a gallery",
    "default_config": {
      "images": [],
      "display_type": "grid"
    },
    "is_global": true
  },
  {
    "id": 3,
    "name": "Contact Form",
    "code": "contact_form",
    "icon": "email",
    "description": "Form for user inquiries",
    "default_config": {
      "fields": [
        {"name": "name", "label": "Name", "type": "text", "required": true},
        {"name": "email", "label": "Email", "type": "email", "required": true},
        {"name": "message", "label": "Message", "type": "textarea", "required": true}
      ],
      "submit_button_text": "Send"
    },
    "is_global": true
  }
]
```

#### 3.1.5 GET /api/pages/{page_id}/components/ Response
```json
[
  {
    "id": 1,
    "page": 1,
    "component_type": 1,
    "component_type_details": {
      "id": 1,
      "name": "Text Block",
      "code": "text_block",
      "icon": "text_fields",
      "description": "Simple text content block",
      "default_config": {
        "text": "Default text content",
        "style": "default"
      },
      "is_global": true
    },
    "title": "Welcome Text",
    "instance_id": "welcome-text-1",
    "config": {
      "text": "<h1>Welcome to our website</h1><p>This is our homepage content.</p>",
      "style": "modern"
    },
    "position": {
      "x": 0,
      "y": 0,
      "w": 12,
      "h": 4
    },
    "data_source": null
  },
  {
    "id": 2,
    "page": 1,
    "component_type": 2,
    "component_type_details": {
      "id": 2,
      "name": "Image Gallery",
      "code": "image_gallery",
      "icon": "collections",
      "description": "Display multiple images in a gallery",
      "default_config": {
        "images": [],
        "display_type": "grid"
      },
      "is_global": true
    },
    "title": "Featured Images",
    "instance_id": "featured-images-1",
    "config": {
      "images": [
        {
          "url": "/media/images/image1.jpg",
          "caption": "Image 1"
        },
        {
          "url": "/media/images/image2.jpg",
          "caption": "Image 2"
        }
      ],
      "display_type": "carousel"
    },
    "position": {
      "x": 0,
      "y": 4,
      "w": 12,
      "h": 6
    },
    "data_source": null
  }
]
```

#### 3.1.6 GET /api/pages/{page_id}/components/{id}/ Response
```json
{
  "id": 1,
  "page": 1,
  "component_type": 1,
  "component_type_details": {
    "id": 1,
    "name": "Text Block",
    "code": "text_block",
    "icon": "text_fields",
    "description": "Simple text content block",
    "default_config": {
      "text": "Default text content",
      "style": "default"
    },
    "is_global": true
  },
  "title": "Welcome Text",
  "instance_id": "welcome-text-1",
  "config": {
    "text": "<h1>Welcome to our website</h1><p>This is our homepage content.</p>",
    "style": "modern"
  },
  "position": {
    "x": 0,
    "y": 0,
    "w": 12,
    "h": 4
  },
  "data_source": null
}
```

#### 3.1.7 GET /api/pages/{page_id}/layout/ Response
```json
{
  "id": 1,
  "page": 1,
  "layout_config": {
    "columns": 12,
    "rowHeight": 30,
    "containerPadding": [10, 10],
    "margin": [10, 10],
    "isDraggable": true,
    "isResizable": true
  }
}
```

#### 3.1.8 GET /api/session-analytics/daily_sessions/ Response
```json
{
  "data": [
    { "date": "01 Apr, 2025", "count": 35 },
    { "date": "02 Apr, 2025", "count": 40 },
    { "date": "03 Apr, 2025", "count": 50 },
    { "date": "04 Apr, 2025", "count": 60 },
    { "date": "05 Apr, 2025", "count": 40 },
    { "date": "06 Apr, 2025", "count": 30 },
    { "date": "07 Apr, 2025", "count": 45 }
  ],
  "days": 7
}
```

**Query Parameters:**
- `days`: Number of days to fetch data for (default: 7)

### 3.2 Error Responses

Error responses follow this format:

```json
{
  "error": "Error message",
  "detail": "Detailed explanation if available",
  "code": "error_code"
}
```

Common status codes:

* **400 Bad Request**: Invalid input data
* **401 Unauthorized**: Missing or invalid API key
* **403 Forbidden**: Valid API key but insufficient permissions
* **404 Not Found**: Requested resource doesn't exist
* **405 Method Not Allowed**: The HTTP method is not supported
* **500 Internal Server Error**: Server-side error

## 4. Query Parameters

### 4.1 Filtering

List endpoints support filtering by adding query parameters:

```
GET /api/pages/?is_published=true
GET /api/component-types/?is_global=true
```

### 4.2 Pagination

List endpoints support pagination using:

```
GET /api/pages/?page=2&page_size=10
```

Paginated responses include:

```json
{
  "count": 100,           // Total number of items
  "next": "http://...",  // URL to next page (null if none)
  "previous": null,      // URL to previous page (null if none)
  "results": [...]       // Array of items for current page
}
```

## 5. Workflow Examples

### 5.1 Create a New Page

1. **Create the page**:
   ```
   POST /api/pages/
   {
     "title": "New Page", 
     "slug": "new-page",
     "description": "Description"
   }
   ```
   
   Success response (201 Created):
   ```json
   {
     "id": 123,
     "title": "New Page",
     "slug": "new-page",
     "description": "Description",
     "is_published": false,
     "created_at": "2025-04-01T10:00:00Z",
     "updated_at": "2025-04-01T10:00:00Z",
     "layout": {
       "id": 45,
       "layout_config": {"columns": 12, "rowHeight": 30}
     },
     "components": []
   }
   ```

2. **Add components** (after page creation):
   ```
   POST /api/pages/123/components/
   {
     "component_type": 1,
     "title": "Banner",
     "instance_id": "banner-1",
     "config": {"text": "Welcome"},
     "position": {"x": 0, "y": 0, "w": 12, "h": 3}
   }
   ```
   
   Success response (201 Created):
   ```json
   {
     "id": 456,
     "page": 123,
     "component_type": 1,
     "component_type_details": {
       "id": 1,
       "name": "Banner",
       "code": "banner",
       "icon": "banner-icon",
       "description": "A banner component",
       "default_config": {},
       "is_global": true
     },
     "title": "Banner",
     "instance_id": "banner-1",
     "config": {"text": "Welcome"},
     "position": {"x": 0, "y": 0, "w": 12, "h": 3},
     "data_source": null
   }
   ```

3. **Update layout**:
   ```
   PUT /api/pages/123/layout/
   {
     "layout_config": {
       "columns": 12,
       "rowHeight": 30,
       "containerPadding": [10, 10]
     }
   }
   ```
   
   Success response (200 OK):
   ```json
   {
     "id": 45,
     "page": 123,
     "layout_config": {
       "columns": 12,
       "rowHeight": 30,
       "containerPadding": [10, 10]
     }
   }
   ```

### 5.2 Full Page Update (Single Call)

```
PUT /api/pages/123/full-update/
{
  "page": {
    "title": "Updated Title",
    "description": "Updated description"
  },
  "layout": {
    "layout_config": {
      "columns": 12,
      "rowHeight": 40
    }
  },
  "components": [
    {
      "id": 456,
      "title": "Updated Banner",
      "position": {"x": 0, "y": 0, "w": 12, "h": 4}
    },
    {
      "component_type": 2,
      "title": "New Text Block",
      "instance_id": "text-1",
      "config": {"content": "Hello world"},
      "position": {"x": 0, "y": 4, "w": 6, "h": 2}
    }
  ],
  "removed_components": [789]
}
```

Success response (200 OK) - returns the complete updated page with all data.

### 5.3 Publish a Page

```
POST /api/pages/123/publish/
{
  "is_published": true
}
```

Success response (200 OK) - returns the updated page.

### 5.4 Error Handling Example

If you try to create a component with an invalid component_type:

```
POST /api/pages/123/components/
{
  "component_type": 9999,
  "title": "Banner",
  "instance_id": "banner-1"
}
```

Error response (400 Bad Request):
```json
{
  "error": "Invalid input",
  "detail": {
    "component_type": ["Invalid pk '9999' - object does not exist."]
  }
}
```

### 5.5 Delete a Page with Components

```
DELETE /api/pages/123/delete/
```

Success response (204 No Content) - the page and all its components are deleted.

Note: This endpoint permanently deletes the page and its components. Use with caution.
