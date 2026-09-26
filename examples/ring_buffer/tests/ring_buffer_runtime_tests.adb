--  Executable tests of the production Ring_Buffer API.
--
--  Uses only the public, non-ghost API; it never inspects Content, First or
--  Length. Behaviour is checked with explicit comparisons, so the tests are
--  meaningful in both build configurations:
--
--    default                     production build, ghost code not compiled
--    -XRING_BUFFER_ASSERTIONS=on -gnata: every contract, including the ghost
--                                Model and the functional-sequence
--                                postconditions, is also executed

with Ada.Command_Line;
with Ada.Text_IO; use Ada.Text_IO;
with Ring_Buffer;  use Ring_Buffer;

procedure Ring_Buffer_Runtime_Tests with SPARK_Mode => Off is

   Failures : Natural := 0;
   Checks   : Natural := 0;

   procedure Check (Condition : Boolean; Message : String) is
   begin
      Checks := Checks + 1;
      if not Condition then
         Failures := Failures + 1;
         Put_Line ("FAIL: " & Message);
      end if;
   end Check;

   procedure Expect_Pop (Q : in out Buffer; Expected : Element; Ctx : String)
   is
      Seen : Element;
   begin
      Check (not Is_Empty (Q), Ctx & ": buffer unexpectedly empty");
      if not Is_Empty (Q) then
         Pop (Q, Seen);
         Check (Seen = Expected,
                Ctx & ": popped" & Seen'Image & " expected" & Expected'Image);
      end if;
   end Expect_Pop;

   procedure Test_Initial_Empty is
      Q : Buffer;
   begin
      Initialize (Q);
      Check (Is_Empty (Q), "initial: Is_Empty");
      Check (not Is_Full (Q), "initial: not Is_Full");
   end Test_Initial_Empty;

   procedure Test_Push_One is
      Q : Buffer;
      E : Element;
   begin
      Initialize (Q);
      Push (Q, 42);
      Check (not Is_Empty (Q), "push one: not empty");
      Check (not Is_Full (Q), "push one: not full");
      Peek (Q, E);
      Check (E = 42, "push one: peek");
      Expect_Pop (Q, 42, "push one");
      Check (Is_Empty (Q), "push one: empty after pop");
   end Test_Push_One;

   procedure Test_Push_Multiple_FIFO is
      Q : Buffer;
      E : Element;
   begin
      Initialize (Q);
      for V in 1 .. 5 loop
         Push (Q, V * 10);
      end loop;
      Peek (Q, E);
      Check (E = 10, "fifo: peek first");
      Peek (Q, E);
      Check (E = 10, "fifo: peek does not consume");
      for V in 1 .. 5 loop
         Expect_Pop (Q, V * 10, "fifo" & V'Image);
      end loop;
      Check (Is_Empty (Q), "fifo: empty at end");
   end Test_Push_Multiple_FIFO;

   procedure Test_Clear is
      Q : Buffer;
   begin
      Initialize (Q);
      for V in 1 .. 7 loop
         Push (Q, V);
      end loop;
      Clear (Q);
      Check (Is_Empty (Q), "clear: empty");
      Check (not Is_Full (Q), "clear: not full");
      Push (Q, 99);
      Expect_Pop (Q, 99, "clear: reuse");
      Check (Is_Empty (Q), "clear: empty after reuse");
   end Test_Clear;

   procedure Test_Full_And_Empty_Boundaries is
      Q : Buffer;
   begin
      Initialize (Q);
      for V in 1 .. Max_Size loop
         Check (not Is_Full (Q), "full boundary: not full before" & V'Image);
         Push (Q, V);
      end loop;
      Check (Is_Full (Q), "full boundary: full at Max_Size");
      Check (not Is_Empty (Q), "full boundary: not empty");
      for V in 1 .. Max_Size loop
         Check (not Is_Empty (Q), "empty boundary: not empty before" & V'Image);
         Expect_Pop (Q, V, "full drain" & V'Image);
      end loop;
      Check (Is_Empty (Q), "empty boundary: empty after draining");
      Check (not Is_Full (Q), "empty boundary: not full");
   end Test_Full_And_Empty_Boundaries;

   procedure Test_Wraparound is
      Q : Buffer;
   begin
      Initialize (Q);
      --  Advance First to the middle, then push across the physical end.
      for V in 1 .. 10 loop
         Push (Q, V);
      end loop;
      for V in 1 .. 10 loop
         Expect_Pop (Q, V, "wrap setup" & V'Image);
      end loop;
      for V in 100 .. 100 + Max_Size - 1 loop
         Push (Q, V);
      end loop;
      Check (Is_Full (Q), "wrap: full after wrapping fill");
      for V in 100 .. 100 + Max_Size - 1 loop
         Expect_Pop (Q, V, "wrap drain" & V'Image);
      end loop;
      Check (Is_Empty (Q), "wrap: empty");
   end Test_Wraparound;

   procedure Test_Multiple_Wraparounds is
      Q        : Buffer;
      Next_In  : Element := 0;
      Next_Out : Element := 0;
   begin
      Initialize (Q);
      --  Keep 5 elements live and cycle 10 * Max_Size elements through.
      for I in 1 .. 5 loop
         Push (Q, Next_In);
         Next_In := Next_In + 1;
      end loop;
      for Round in 1 .. 10 * Max_Size loop
         Push (Q, Next_In);
         Next_In := Next_In + 1;
         Expect_Pop (Q, Next_Out, "multi-wrap round" & Round'Image);
         Next_Out := Next_Out + 1;
      end loop;
      for I in 1 .. 5 loop
         Expect_Pop (Q, Next_Out, "multi-wrap tail" & I'Image);
         Next_Out := Next_Out + 1;
      end loop;
      Check (Is_Empty (Q), "multi-wrap: empty at end");
      Check (Next_Out = Next_In, "multi-wrap: all elements drained");
   end Test_Multiple_Wraparounds;

   procedure Test_Fill_Drain_Refill is
      Q : Buffer;
   begin
      Initialize (Q);
      for V in 1 .. Max_Size loop
         Push (Q, V);
      end loop;
      for V in 1 .. 11 loop
         Expect_Pop (Q, V, "partial drain" & V'Image);
      end loop;
      for V in 201 .. 211 loop
         Push (Q, V);
      end loop;
      Check (Is_Full (Q), "refill: full");
      for V in 12 .. Max_Size loop
         Expect_Pop (Q, V, "refill drain old" & V'Image);
      end loop;
      for V in 201 .. 211 loop
         Expect_Pop (Q, V, "refill drain new" & V'Image);
      end loop;
      Check (Is_Empty (Q), "refill: empty at end");
   end Test_Fill_Drain_Refill;

begin
   Test_Initial_Empty;
   Test_Push_One;
   Test_Push_Multiple_FIFO;
   Test_Clear;
   Test_Full_And_Empty_Boundaries;
   Test_Wraparound;
   Test_Multiple_Wraparounds;
   Test_Fill_Drain_Refill;

   if Failures = 0 then
      Put_Line ("ring_buffer runtime tests: PASS (" & Checks'Image
                & " checks)");
   else
      Put_Line ("ring_buffer runtime tests: FAIL (" & Failures'Image
                & " of" & Checks'Image & " checks failed)");
      Ada.Command_Line.Set_Exit_Status (Ada.Command_Line.Failure);
   end if;
end Ring_Buffer_Runtime_Tests;
