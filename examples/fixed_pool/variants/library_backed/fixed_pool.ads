with SPARK.Big_Integers; use SPARK.Big_Integers;
with SPARK.Containers.Functional.Sets;
private with SPARK_Refine_Prefix_Sets;

package Fixed_Pool with SPARK_Mode is
   Max_Objects : constant := 32;

   subtype Object_Id is Positive range 1 .. Max_Objects;
   subtype Pool_Count is Natural range 0 .. Max_Objects;

   --  Abstract model: the mathematical set of currently free identities.
   --  An identity is allocated iff it is not in this set (complement over
   --  the finite Object_Id universe), so no separate allocated set exists.
   package Id_Sets is new SPARK.Containers.Functional.Sets
     (Element_Type => Object_Id);
   use type Id_Sets.Set;

   type Pool is private;

   function Free_Model (P : Pool) return Id_Sets.Set
   with Ghost,
        Post => Id_Sets.Length (Free_Model'Result)
                <= To_Big_Integer (Max_Objects);

   function Free_Count (P : Pool) return Pool_Count
   with Post => To_Big_Integer (Free_Count'Result)
                = Id_Sets.Length (Free_Model (P));

   function Is_Free (P : Pool; Id : Object_Id) return Boolean
   with Post => Is_Free'Result = Id_Sets.Contains (Free_Model (P), Id);

   function Is_Allocated (P : Pool; Id : Object_Id) return Boolean
   with Post => Is_Allocated'Result
                = not Id_Sets.Contains (Free_Model (P), Id);

   function Is_Exhausted (P : Pool) return Boolean
   with Post => Is_Exhausted'Result = Id_Sets.Is_Empty (Free_Model (P));

   procedure Initialize (P : out Pool)
   with Post => Free_Count (P) = Max_Objects
                and (for all Id in Object_Id =>
                       Id_Sets.Contains (Free_Model (P), Id));

   procedure Allocate (P : in out Pool; Id : out Object_Id)
   with Pre  => Free_Count (P) > 0,
        Post => Id_Sets.Contains (Free_Model (P)'Old, Id)
                and Free_Model (P)
                    = Id_Sets.Remove (Free_Model (P)'Old, Id)
                and Free_Count (P) = Free_Count (P)'Old - 1;

   procedure Release (P : in out Pool; Id : Object_Id)
   with Pre  => Is_Allocated (P, Id),
        Post => Free_Model (P) = Id_Sets.Add (Free_Model (P)'Old, Id)
                and Free_Count (P) = Free_Count (P)'Old + 1;

private
   type Free_Array is array (Object_Id) of Object_Id;

   --  Task 004: the prefix-set proof pattern comes from the reusable
   --  library (proof_patterns/); only this configuration is per instance.
   package Free_Prefix is new SPARK_Refine_Prefix_Sets
     (Element_Type  => Object_Id,
      Index_Type    => Object_Id,
      Storage_Array => Free_Array,
      Element_Sets  => Id_Sets);

   type Pool is record
      Free_Stack : Free_Array;
      Top        : Pool_Count := 0;
   end record
   with Type_Invariant => Free_Prefix.Is_Unique (Pool.Free_Stack, Pool.Top);

end Fixed_Pool;
