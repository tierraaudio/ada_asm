## ADDED Requirements

### Requirement: Clicking the bell opens a notification panel anchored under it

The frontend SHALL surface in-app notifications via a panel that opens when the user clicks the `NotificationBell` in the Header. The bell + panel pair is composed inside a single `NotificationMenu` component that owns the popover open/close state (Radix Popover). The panel is anchored under the bell, on the right side of the Header, 384 px wide. The implementation MUST be pixel-faithful to Figma `47:14343` at the `lg` breakpoint.

#### Scenario: Clicking the bell opens the panel

- **WHEN** the user clicks the notification bell button in the Header
- **THEN** a popover panel appears anchored beneath the bell on the right side of the Header
- **AND** the popover width is 384 px

#### Scenario: The panel closes on Escape

- **WHEN** the panel is open and the user presses `Escape`
- **THEN** the panel is hidden
- **AND** focus returns to the bell button

#### Scenario: The panel closes on outside-click

- **WHEN** the panel is open and the user clicks anywhere outside both the bell and the panel
- **THEN** the panel is hidden
- **AND** no other side effect is triggered

### Requirement: The panel header shows the title and an unread-count pill

The panel header section SHALL contain, on a single row separated by `justify-between`:
- A heading "Notificaciones" rendered as Inter Medium 18 px in `text-text-primary` (`#1a1a1a`).
- A magenta pill (`bg-brand`, white text, fully rounded, ~24 px tall, padding-x ~8 px) on the right with the live unread count followed by `" nuevas"` (e.g., `"2 nuevas"`). When the unread count is 0 the pill is not rendered.

A 1 px bottom border separates the header from the list.

#### Scenario: Header renders the static heading and the unread pill

- **WHEN** the panel is open and the unread count is 2
- **THEN** the panel header shows the text `Notificaciones` on the left and a magenta pill with `2 nuevas` on the right

#### Scenario: The unread pill is hidden when unread count is zero

- **WHEN** the panel is open and the unread count is 0
- **THEN** the magenta pill is not rendered

### Requirement: The panel renders a scrollable list of notification items

The panel body SHALL render the notifications as a vertical scrollable list (max-height ~500 px). Each item:
- Is ~117 px tall.
- Has a 1 px bottom divider (no divider on the last item).
- Renders a title (14 px Inter Medium, `text-text-primary`), a subtitle (12 px Inter Regular, `text-text-secondary`), and a timestamp (12 px Inter Regular, `text-text-secondary`).
- When the item's `read` flag is `false`, the item's background uses the light magenta tint `rgba(233,30,140,0.05)` and a 8 px magenta dot is rendered at the item's top-right corner.

#### Scenario: Unread items are tinted and carry a dot

- **WHEN** the panel is open and at least one item has `read: false`
- **THEN** that item has a background of `rgba(233,30,140,0.05)` and an 8 px circular magenta indicator at the top-right

#### Scenario: Read items have no tint and no dot

- **WHEN** the panel is open and an item has `read: true`
- **THEN** that item has the default background (transparent over the panel's white) and no magenta dot

### Requirement: The panel footer links to a full notifications view

The panel footer SHALL contain a centred link "Ver todas las notificaciones" in `text-brand` (magenta), Inter Medium 14 px, separated from the list by a 1 px top border. The link's `href` is `/notifications`. The route target does not yet exist; clicking is allowed but the destination will render the placeholder shell until the dedicated notifications page lands in a future US.

#### Scenario: Footer link is visible and routes

- **WHEN** the panel is open
- **THEN** the footer renders a `<a>` (or `NavLink`) with text "Ver todas las notificaciones"
- **AND** the link's `href` ends with `/notifications`

### Requirement: Notification data is sourced from a hook (placeholder feed for this change)

The component MUST read notifications from a `useNotifications()` hook. For this change the hook returns a hardcoded array of six placeholder notifications matching the Figma copy (two unread). The hook's return type is `{ items: Notification[]; unreadCount: number; }`. The hook is the seam that a future US will replace with a real backend-fed source without touching the rendering components.

#### Scenario: Hook returns the placeholder feed

- **WHEN** `useNotifications()` is called
- **THEN** the returned `items` array has length 6
- **AND** the `items` whose copy matches the two Figma "unread" examples have `read: false`
- **AND** `unreadCount` equals the count of unread items in `items`

### Requirement: Panel is keyboard accessible

The panel SHALL be keyboard-reachable end-to-end:
- Tab from the bell opens (or moves into) the panel.
- Inside the panel, focus cycles through the focusable elements (the footer link is focusable; items are not interactive in this change).
- `Escape` closes the panel and returns focus to the bell.

#### Scenario: Tab and Escape behaviour

- **WHEN** the bell is focused and the user presses Enter
- **THEN** the panel opens
- **WHEN** the user presses Tab
- **THEN** focus moves to the "Ver todas las notificaciones" footer link
- **WHEN** the user presses Escape
- **THEN** the panel closes and focus is back on the bell
