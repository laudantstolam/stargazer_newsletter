### Usage
1. fork current repo
2. add GH_PAT in repo secret with granted the `user:read`, `user:following` permissoin
3. Trigger in action or wait for cron job works

### Defaults
- Triggers
```
on:
  schedule:
    - cron: '0 9 * * 1' (Monday 9:00 AM)
  workflow_dispatch: (Manual Trigger)
```

it follows:`<minutes> <hours> <day> <month> <day in the week>`, `*` means all

### Format
see samples in my [issue](https://github.com/laudantstolam/stargazer_newsletter/issues)