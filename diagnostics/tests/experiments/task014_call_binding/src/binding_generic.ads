--  Task 014 experimental corpus, Family E: a generic whose Pre is
--  written once in the template and reached through an instance.
generic
   type T is range <>;
package Binding_Generic with SPARK_Mode is

   procedure Check (X : T)
   with Pre    => X > 0
                  and then X < 100,
        Global => null;

end Binding_Generic;
