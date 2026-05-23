## MODIFIED Requirements

### Requirement: The Header hosts a user menu pill matching the Figma design

The Header SHALL render a `UserMenuPill` component on the right side, pixel-faithful to Figma node `37:45` at the `lg` breakpoint. The pill consists of, in this order from left to right: a 36 px notification bell button with an 8 px red status dot at its top-right (the bell now opens a notification panel — see capability `in-app-notifications`); a clickable pill (52 px tall) containing a 32 px magenta avatar circle with a person icon, two stacked text lines (`full_name` in 14 px medium `#1a1a1a`, then `Administrator` / `User` in 12 px medium `#6b6b6b`), and a 16 px chevron-down icon. The avatar circle MUST use the brand magenta token. The pill is keyboard reachable; activating it toggles the dropdown.

#### Scenario: Pill renders the authenticated user's identity

- **WHEN** the auth store status is `authenticated` and `user.full_name = "Admin User"`, `user.global_role = "admin"`
- **THEN** the Header renders a button labelled "Admin User" with the role text "Administrator"
- **AND** the avatar circle background uses the brand magenta CSS variable
- **AND** the bell button is visible

#### Scenario: Role text reflects the user's global_role

- **WHEN** the authenticated user has `global_role = "user"`
- **THEN** the secondary line of the pill displays "User" (capitalised) instead of "Administrator"

#### Scenario: Bell is interactive and opens the notification panel

- **WHEN** the user clicks the notification bell adjacent to the pill
- **THEN** the notification panel from capability `in-app-notifications` opens
- **AND** the user menu dropdown is NOT opened
