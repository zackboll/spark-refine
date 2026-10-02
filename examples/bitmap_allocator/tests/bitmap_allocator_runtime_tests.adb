with Ada.Text_IO; use Ada.Text_IO;
with Bitmap_Allocator; use Bitmap_Allocator;

procedure Bitmap_Allocator_Runtime_Tests with SPARK_Mode => Off is
   type Flags is array (Object_Id) of Boolean;
   P : Pool;
   Free : Flags := [others => True];
   Id : Object_Id;
   Checks : Natural := 0;
   procedure Check (Condition : Boolean) is
   begin
      Checks := Checks + 1;
      if not Condition then
         raise Program_Error with "bitmap mismatch at check" & Checks'Image;
      end if;
   end Check;
   procedure Consistent is
      N : Natural := 0;
   begin
      for J in Object_Id loop
         Check (Is_Free (P, J) = Free (J));
         if Free (J) then N := N + 1; end if;
      end loop;
      Check (Free_Count (P) = N);
      Check (Is_Exhausted (P) = (N = 0));
   end Consistent;
begin
   for Cycle in 1 .. 3 loop
      Initialize (P);
      Free := [others => True];
      Consistent;
      Check (Is_Free (P, 0) and Is_Free (P, 31) and Is_Free (P, 32)
             and Is_Free (P, 63) and Is_Free (P, 64) and Is_Free (P, 69));
      for J in Object_Id loop
         Allocate (P, Id);
         Check (Free (Id));
         Free (Id) := False;
         Consistent;
      end loop;
      Check (Is_Exhausted (P));
      for J in reverse Object_Id loop
         Release (P, J);
         Free (J) := True;
         Consistent;
      end loop;
      for J in Object_Id loop
         Allocate (P, Id);
         Free (Id) := False;
         Release (P, Id);
         Free (Id) := True;
         Consistent;
      end loop;
   end loop;
   Put_Line ("bitmap runtime: " & Checks'Image & " checks passed");
end Bitmap_Allocator_Runtime_Tests;