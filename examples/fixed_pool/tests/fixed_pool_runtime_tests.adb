--  Executable tests of the production Fixed_Pool API.
--
--  Uses only the public, non-ghost API (Initialize, Allocate, Release,
--  Is_Free, Is_Allocated, Free_Count, Is_Exhausted); it never inspects the
--  private free stack. A test-local Held array records which identities the
--  test believes it owns, and every expectation is an explicit comparison.
--
--  No test relies on LIFO order: the identity returned by Allocate is only
--  required to be some identity that the test does not already hold.

with Ada.Command_Line;
with Ada.Text_IO; use Ada.Text_IO;
with Fixed_Pool;  use Fixed_Pool;

procedure Fixed_Pool_Runtime_Tests with SPARK_Mode => Off is

   Failures : Natural := 0;
   Checks   : Natural := 0;

   type Id_Flags is array (Object_Id) of Boolean;

   procedure Check (Condition : Boolean; Message : String) is
   begin
      Checks := Checks + 1;
      if not Condition then
         Failures := Failures + 1;
         Put_Line ("FAIL: " & Message);
      end if;
   end Check;

   --  Every identity's public status must match the test's own record of
   --  held identities, and Free_Count must equal the number not held.
   procedure Check_Consistent (P : Pool; Held : Id_Flags; Ctx : String) is
      Free : Natural := 0;
   begin
      for Id in Object_Id loop
         Check (Is_Allocated (P, Id) = Held (Id),
                Ctx & ": Is_Allocated mismatch for" & Id'Image);
         Check (Is_Free (P, Id) = not Held (Id),
                Ctx & ": Is_Free mismatch for" & Id'Image);
         if not Held (Id) then
            Free := Free + 1;
         end if;
      end loop;
      Check (Free_Count (P) = Free,
             Ctx & ": Free_Count" & Free_Count (P)'Image
             & " expected" & Free'Image);
      Check (Is_Exhausted (P) = (Free = 0), Ctx & ": Is_Exhausted");
   end Check_Consistent;

   --  Allocate one identity; it must not already be held by the test.
   procedure Take
     (P : in out Pool; Held : in out Id_Flags; Id : out Object_Id;
      Ctx : String)
   is
   begin
      Id := Object_Id'First;
      Check (not Is_Exhausted (P), Ctx & ": unexpectedly exhausted");
      if Is_Exhausted (P) then
         return;
      end if;
      Allocate (P, Id);
      Check (not Held (Id),
             Ctx & ": Allocate returned already-held" & Id'Image);
      Check (Is_Allocated (P, Id), Ctx & ": allocated id not allocated");
      Held (Id) := True;
   end Take;

   procedure Give
     (P : in out Pool; Held : in out Id_Flags; Id : Object_Id; Ctx : String)
   is
   begin
      Check (Held (Id), Ctx & ": test releasing an id it does not hold");
      Release (P, Id);
      Held (Id) := False;
      Check (Is_Free (P, Id), Ctx & ": released id not free");
   end Give;

   procedure Test_Initial is
      P    : Pool;
      Held : constant Id_Flags := [others => False];
   begin
      Initialize (P);
      Check (Free_Count (P) = Max_Objects, "initial: Free_Count");
      Check (not Is_Exhausted (P), "initial: not exhausted");
      Check_Consistent (P, Held, "initial");
   end Test_Initial;

   procedure Test_Allocate_One is
      P    : Pool;
      Held : Id_Flags := [others => False];
      A    : Object_Id;
   begin
      Initialize (P);
      Take (P, Held, A, "allocate one");
      Check (Free_Count (P) = Max_Objects - 1, "allocate one: Free_Count");
      Check_Consistent (P, Held, "allocate one");
   end Test_Allocate_One;

   procedure Test_Allocate_Multiple is
      P       : Pool;
      Held    : Id_Flags := [others => False];
      A, B, C : Object_Id;
   begin
      Initialize (P);
      Take (P, Held, A, "allocate multiple");
      Take (P, Held, B, "allocate multiple");
      Take (P, Held, C, "allocate multiple");
      Check (A /= B and B /= C and A /= C, "allocate multiple: distinct");
      Check (Free_Count (P) = Max_Objects - 3,
             "allocate multiple: Free_Count");
      Check_Consistent (P, Held, "allocate multiple");
   end Test_Allocate_Multiple;

   --  Allocate everything: each identity exactly once, then exhausted.
   procedure Test_Allocate_All is
      P    : Pool;
      Held : Id_Flags := [others => False];
      Id   : Object_Id;
   begin
      Initialize (P);
      for N in 1 .. Max_Objects loop
         Take (P, Held, Id, "allocate all");
         Check (Free_Count (P) = Max_Objects - N, "allocate all: count");
      end loop;
      Check (Held = [Object_Id => True],
             "allocate all: every identity returned exactly once");
      Check (Is_Exhausted (P), "allocate all: exhausted");
      Check (Free_Count (P) = 0, "allocate all: Free_Count = 0");
      Check_Consistent (P, Held, "allocate all");
   end Test_Allocate_All;

   --  Release one of several; the others stay allocated.
   procedure Test_Release_One is
      P       : Pool;
      Held    : Id_Flags := [others => False];
      A, B, C : Object_Id;
   begin
      Initialize (P);
      Take (P, Held, A, "release one");
      Take (P, Held, B, "release one");
      Take (P, Held, C, "release one");
      Give (P, Held, B, "release one");
      Check (Is_Free (P, B), "release one: B free");
      Check (Is_Allocated (P, A) and Is_Allocated (P, C),
             "release one: A and C still allocated");
      Check (Free_Count (P) = Max_Objects - 2, "release one: Free_Count");
      Check_Consistent (P, Held, "release one");
   end Test_Release_One;

   --  Allocate everything, release everything in allocation order (the
   --  opposite of stack order); the pool is fully free again.
   procedure Test_Release_All is
      P     : Pool;
      Held  : Id_Flags := [others => False];
      Order : array (1 .. Max_Objects) of Object_Id;
   begin
      Initialize (P);
      for N in Order'Range loop
         Take (P, Held, Order (N), "release all");
      end loop;
      for N in Order'Range loop
         Give (P, Held, Order (N), "release all");
         Check (Free_Count (P) = N, "release all: count");
      end loop;
      Check (Free_Count (P) = Max_Objects, "release all: Free_Count");
      Check (not Is_Exhausted (P), "release all: not exhausted");
      Check_Consistent (P, Held, "release all");
   end Test_Release_All;

   --  Repeated full allocate / release cycles.
   procedure Test_Cycles is
      P    : Pool;
      Held : Id_Flags := [others => False];
      Id   : Object_Id;
   begin
      Initialize (P);
      for Cycle in 1 .. 5 loop
         for N in 1 .. Max_Objects loop
            Take (P, Held, Id, "cycles");
         end loop;
         Check (Is_Exhausted (P), "cycles: exhausted");
         Check (Held = [Object_Id => True], "cycles: all held");
         for R in reverse Object_Id loop
            Give (P, Held, R, "cycles");
         end loop;
         Check (Free_Count (P) = Max_Objects,
                "cycles: all free after cycle" & Cycle'Image);
      end loop;
      Check_Consistent (P, Held, "cycles");
   end Test_Cycles;

   --  Interleaved allocate / release driven by a fixed pseudo-random
   --  sequence, with full consistency checks after every step.
   procedure Test_Interleaved is
      P    : Pool;
      Held : Id_Flags := [others => False];
      Seed : Natural := 12345;
      Id   : Object_Id;

      function Next return Natural is
      begin
         Seed := (Seed * 1103 + 12849) mod 65_536;
         return Seed;
      end Next;
   begin
      Initialize (P);
      for Step in 1 .. 2_000 loop
         if Next mod 3 /= 0 and then not Is_Exhausted (P) then
            Take (P, Held, Id, "interleaved");
         else
            declare
               Cand : Object_Id := Object_Id (Next mod Max_Objects + 1);
            begin
               for K in 1 .. Max_Objects loop
                  exit when Held (Cand);
                  Cand := (if Cand = Max_Objects then 1 else Cand + 1);
               end loop;
               if Held (Cand) then
                  Give (P, Held, Cand, "interleaved");
               end if;
            end;
         end if;
         Check_Consistent (P, Held, "interleaved step" & Step'Image);
      end loop;
   end Test_Interleaved;

begin
   Test_Initial;
   Test_Allocate_One;
   Test_Allocate_Multiple;
   Test_Allocate_All;
   Test_Release_One;
   Test_Release_All;
   Test_Cycles;
   Test_Interleaved;

   if Failures = 0 then
      Put_Line ("PASS:" & Checks'Image & " checks");
   else
      Put_Line ("FAILED:" & Failures'Image & " of" & Checks'Image
                & " checks");
      Ada.Command_Line.Set_Exit_Status (Ada.Command_Line.Failure);
   end if;
end Fixed_Pool_Runtime_Tests;
