with Ada.Command_Line;
with Ada.Text_IO;

procedure Spark_Refine is
   use Ada.Command_Line;
   use Ada.Text_IO;

   Version : constant String := "0.0.0-dev";

   procedure Print_Help is
   begin
      Put_Line ("spark_refine " & Version);
      Put_Line ("Proof-engineering automation for SPARK refinement models.");
      New_Line;
      Put_Line ("Usage:");
      Put_Line ("  spark_refine --help");
      Put_Line ("  spark_refine --version");
      Put_Line ("  spark_refine validate   # planned");
      Put_Line ("  spark_refine generate   # planned");
      Put_Line ("  spark_refine check      # planned");
      New_Line;
      Put_Line ("This bootstrap CLI does not generate proof artifacts yet.");
   end Print_Help;

begin
   if Argument_Count = 0 or else Argument (1) = "--help" or else Argument (1) = "-h" then
      Print_Help;
   elsif Argument (1) = "--version" then
      Put_Line (Version);
   elsif Argument (1) = "validate"
     or else Argument (1) = "generate"
     or else Argument (1) = "check"
   then
      Put_Line ("Command '" & Argument (1) & "' is specified but not implemented in the bootstrap repository.");
      Set_Exit_Status (Failure);
   else
      Put_Line ("Unknown command: " & Argument (1));
      Put_Line ("Run spark_refine --help for usage.");
      Set_Exit_Status (Failure);
   end if;
end Spark_Refine;
