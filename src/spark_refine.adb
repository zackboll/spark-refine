with Ada.Command_Line;
with Ada.Text_IO;

procedure Spark_Refine is
   use Ada.Command_Line;
   use Ada.Text_IO;

   Version : constant String := "0.0.0-dev";

   procedure Print_Help is
   begin
      Put_Line ("spark_refine " & Version);
      Put_Line ("Legacy/bootstrap Ada executable of the spark-refine project");
      Put_Line ("(reusable proof patterns and proof-aware diagnostics for SPARK).");
      New_Line;
      Put_Line ("Usage:");
      Put_Line ("  spark_refine --help");
      Put_Line ("  spark_refine --version");
      New_Line;
      Put_Line ("This executable implements no commands. The current");
      Put_Line ("developer-facing diagnostics CLI is a separate Python program,");
      Put_Line ("installed from diagnostics/ and invoked with a HYPHEN:");
      New_Line;
      Put_Line ("    python3 -m pip install ./diagnostics");
      Put_Line ("    spark-refine explain");
      New_Line;
      Put_Line ("spark_refine (underscore, this Ada program) and spark-refine");
      Put_Line ("(hyphen, the Python CLI) are distinct executables.");
      New_Line;
      Put_Line ("Historical/deprioritized research (not planned commands):");
      Put_Line ("  validate, generate, check -- source generation was");
      Put_Line ("  investigated in Tasks 001-004 and deliberately deprioritized.");
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
      Put_Line ("Command '" & Argument (1) & "' is historical/deprioritized research"
                & " and is not implemented.");
      Put_Line ("For proof diagnostics use the Python CLI: spark-refine explain");
      Set_Exit_Status (Failure);
   elsif Argument (1) = "explain"
     or else Argument (1) = "analyze"
     or else Argument (1) = "compare-provers"
     or else Argument (1) = "rules"
   then
      Put_Line ("'" & Argument (1) & "' is a command of the Python CLI spark-refine"
                & " (hyphen), not of this Ada executable spark_refine (underscore).");
      Put_Line ("Install it with: python3 -m pip install ./diagnostics");
      Put_Line ("Then run:        spark-refine " & Argument (1));
      Set_Exit_Status (Failure);
   else
      Put_Line ("Unknown command: " & Argument (1));
      Put_Line ("Run spark_refine --help for usage.");
      Set_Exit_Status (Failure);
   end if;
end Spark_Refine;
