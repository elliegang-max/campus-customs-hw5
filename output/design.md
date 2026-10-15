# The desk: what it looks like, and why

**Layout.** The board is a clean three-column desk — tickets on the left, the
agent workspace in the middle, approvals and the run summary on the right —
under a slim top bar carrying the shop's date and the checking balance. The
three columns follow the order the work happens in, so a ticket can be worked
left to right without hunting: pick a tag, watch the team think, sign off what
they ask for. The top bar is deliberately thin — a one-line rule rather than a
hero banner — because the only two facts that matter at all times are *what day
the shop thinks it is* and *how much money is left*, and everything else on
screen should be the work rather than the chrome. The columns collapse to two at
tablet width with the money column spanning the full row, and to a single stack
on a phone, so nothing needs sideways scrolling to read.

**The agents.** Each of the five has its own colour, its own glyph, and a status
pill — Boss indigo ✦, Inventory green ▦, Accounting amber $, Facilities violet
⌂, Customer Service teal ✉ — and that colour follows the agent everywhere it
appears: the roster chip, the left edge of every line it writes in the feed, and
the delegation chain in the summary. One identity used in three places means you
learn it once and can then read the feed by colour alone. The pill says *idle*,
*working*, or *done*, and whoever is working gets a ring that pulses out from
their chip, so a glance tells you who is busy without reading a word. The feed
itself shows what each agent is saying and which tool it reached for, and
failures stay in it, tinted, with their error text intact — a refused payment is
the most interesting thing that can happen on this board, and hiding it would be
the wrong instinct.

**Resolved tickets, and the money.** A ticket that the database reports as
resolved gets a bold **RESOLVED** stamp, thumped on at an angle with an
animation that overshoots and settles the way a real stamp does. It follows the
database rather than the end of a run, so the stamp means the ticket is
genuinely finished and not merely looked at. The checking balance is by a wide
margin the biggest number on the page, set in a serif face with tabular figures
so the digits hold their place, and after an approved payment it **counts down**
over about a second rather than cutting to the new figure. Both choices are
about trust: money leaving the account should be something you watch happen, and
a number that size is hard to miss or misread, which is what you want from the
one figure that constrains every other decision on the desk.

**The touches that make it a desk rather than a dashboard.** The whole thing is
a workshop in warm cream and navy with a single vermilion accent reserved for
decisions — the rule under the shop name, the *send the team in* button, and the
*approve* button, and nothing else. Tickets are drawn as paper tags with a
punched hole, a thread across the top, and each one hung half a degree off
square, straightening when you hover; approvals are till receipts in monospace
with dashed rules, the total in large figures, and a torn bottom edge cut with a
zigzag. Feed lines slide up as they arrive rather than appearing, so the run
reads as something unfolding. The empty states are written like a person talking
— *"Pick a ticket and send the team in"* over the feed, and *"Nothing to
approve. The agents put payments here; they cannot sign them"* over the
approvals column, which quietly teaches the rule the whole system is built
around. All of the motion collapses under `prefers-reduced-motion`. None of this
is decoration for its own sake: a desk someone works at all day should feel like
a place, and the shop it belongs to prints things on paper.
