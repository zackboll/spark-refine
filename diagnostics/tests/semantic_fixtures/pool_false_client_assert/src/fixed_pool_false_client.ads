--  Task 005 diagnostics fixture source (NOT a benchmark source).
--
--  A client of the unchanged, fully proved Task 003 fixed pool whose
--  assertion is simply FALSE: Initialize's public postcondition says
--  Free_Count (P) = Max_Objects (= 32), and the client asserts 0.
--
--  Used only by diagnostics/scripts/capture_fixtures.py to produce the
--  fixture pool_false_client_assert: SRD002 must fire at LOW confidence
--  (client-only VC_ASSERT) and must not claim that any public contract is
--  insufficient, because here no contract is.

with Fixed_Pool; use Fixed_Pool;

package Fixed_Pool_False_Client with SPARK_Mode is

   procedure Initialize_Then_Claim_Empty;

end Fixed_Pool_False_Client;
