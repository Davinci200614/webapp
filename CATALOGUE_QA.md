# Original MACHINATI integration verification

The approximate React catalogue is no longer used. The application uses copies
of the original catalogue, cooperative and operations HTML, isolated in frames
as in the original MACHINATI application. Each original embedded stylesheet is
preserved byte-for-byte and checked against the source hash in the manifest.
The operations request dashboard is ported from the original React component.

Integration changes concern authenticated API access, login gates and functional
bugs; the page structures, original responsive CSS, fonts and imagery are retained.
The original priority algorithm is verified against 192 frozen reference cases.
The full backend suite passed 145 tests; frontend build, route renders and
original-page/authentication regression checks also passed.

Browser verification: BLOCKED. The execution sandbox denies local server socket
creation and the available headless Firefox failed to produce screenshots. Exact
rendered visual parity has not been verified and is not claimed as a test result.

Manual acceptance:

1. Restart the integrated app and open `/`; compare with original MACHINATI at the
   same desktop and phone viewport. The original source pages are now used.
2. Open the catalogue mobile menu; follow cooperative/operations navigation.
3. In a logged-out session, confirm credentials are required before either private
   view mounts. Bad credentials must not reveal request data.
4. Sign in; open Demandes, Matériel, Pilotage and Coopérative. Check priority
   explanations, machine candidates and approve/reject/complete transitions.
5. In the catalogue, combine filters, open a machine request, change duration and
   verify hourly estimate. Confirm WhatsApp opens the configured business number.
6. Check reserved/unavailable machines, empty search results, session expiration
   and logout. A zero-result operations filter must disable request actions.
7. Test the original urgency/date/locality example: critical local request before
   normal remote request under otherwise equivalent circumstances. Verify urgency
   and check that its score rises by 10. Approval is not an automatic booking.

IoT telemetry and route optimization are not implemented in the source repo;
original placeholder panels retain their unavailable-service explanations.
